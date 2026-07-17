/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.gustavguide.engine.condition.AndCondition;
import com.gustavguide.engine.condition.Condition;
import com.gustavguide.engine.condition.ConstantCondition;
import com.gustavguide.engine.condition.ItemAcquiredCondition;
import com.gustavguide.engine.condition.ItemCondition;
import com.gustavguide.engine.condition.ItemConsumedCondition;
import com.gustavguide.engine.condition.NotCondition;
import com.gustavguide.engine.condition.OrCondition;
import com.gustavguide.engine.condition.PositionCondition;
import com.gustavguide.engine.condition.QuestCondition;
import com.gustavguide.engine.condition.QuestPointsCondition;
import com.gustavguide.engine.condition.SkillCondition;
import com.gustavguide.engine.condition.VarbitCondition;
import com.gustavguide.engine.condition.VarpCondition;
import java.util.ArrayList;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;

/**
 * Builds a {@link Condition} tree from the JSON {@code complete} field of a route step.
 *
 * <p>Parsing is fail-safe: any unknown operator, missing field, or unresolved enum yields
 * {@link ConstantCondition#MANUAL} (never auto-completes) rather than throwing, so a data
 * typo degrades a step to manual-advance instead of breaking the whole route or, worse,
 * auto-skipping a step that was never actually done.</p>
 */
@Slf4j
public final class ConditionFactory
{
	private ConditionFactory()
	{
	}

	/**
	 * @param element the {@code complete} JSON element (may be null/absent for manual steps)
	 * @param stepId  step id, for diagnostics
	 * @return a never-null condition; {@link ConstantCondition#MANUAL} on any problem
	 */
	public static Condition parse(JsonElement element, String stepId)
	{
		if (element == null || element.isJsonNull())
		{
			return ConstantCondition.MANUAL;
		}
		try
		{
			return parseNode(element, stepId);
		}
		catch (Exception e)
		{
			log.warn("Gustav's Helper: could not parse condition for step '{}': {}", stepId, e.getMessage());
			return ConstantCondition.MANUAL;
		}
	}

	private static Condition parseNode(JsonElement element, String stepId)
	{
		if (!element.isJsonObject())
		{
			throw new IllegalArgumentException("condition node is not an object");
		}
		JsonObject o = element.getAsJsonObject();
		String op = getString(o, "op", "manual").toLowerCase();

		switch (op)
		{
			case "manual":
				return ConstantCondition.MANUAL;
			case "always":
			case "true":
				return ConstantCondition.ALWAYS_TRUE;
			case "skill":
			{
				Skill skill = Skill.valueOf(getString(o, "skill", "").toUpperCase());
				int level = getInt(o, "level", 1);
				return new SkillCondition(skill, level, Op.fromString(getString(o, "cmp", ">=")));
			}
			case "quest":
			{
				Quest quest = Quest.valueOf(getString(o, "quest", "").toUpperCase());
				QuestState state = parseQuestState(getString(o, "state", "FINISHED"));
				return new QuestCondition(quest, state);
			}
			case "qp":
			case "questpoints":
				return new QuestPointsCondition(getInt(o, "value", 0), Op.fromString(getString(o, "cmp", ">=")));
			case "item":
				return new ItemCondition(getInt(o, "id", -1), getInt(o, "qty", 1),
					ItemScope.fromString(getString(o, "scope", "ANY")));
			case "itembank":
				return new ItemCondition(getInt(o, "id", -1), getInt(o, "qty", 1), ItemScope.BANK);
			case "itemequipped":
			case "itemworn":
				return new ItemCondition(getInt(o, "id", -1), getInt(o, "qty", 1), ItemScope.EQUIPMENT);
			case "iteminventory":
				return new ItemCondition(getInt(o, "id", -1), getInt(o, "qty", 1), ItemScope.INVENTORY);
			case "itemacquired":
			case "acquired":
			{
				int id = getInt(o, "id", -1);
				if (id < 0)
				{
					log.warn("Gustav's Helper: itemAcquired condition missing/invalid id in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new ItemAcquiredCondition(id, getInt(o, "qty", 1));
			}
			case "itemconsumed":
			case "itemspent":
			case "consumed":
			{
				int id = getInt(o, "id", -1);
				if (id < 0)
				{
					log.warn("Gustav's Helper: itemConsumed condition missing/invalid id in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new ItemConsumedCondition(id, getInt(o, "qty", 1));
			}
			case "varbit":
			{
				int id = getInt(o, "id", -1);
				if (id < 0)
				{
					log.warn("Gustav's Helper: varbit condition missing/invalid id in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new VarbitCondition(id, getInt(o, "value", 0), Op.fromString(getString(o, "cmp", ">=")));
			}
			case "varp":
			{
				int id = getInt(o, "id", -1);
				if (id < 0)
				{
					log.warn("Gustav's Helper: varp condition missing/invalid id in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new VarpCondition(id, getInt(o, "value", 0), Op.fromString(getString(o, "cmp", ">=")));
			}
			case "position":
			case "reached":
			{
				// Require explicit x AND y; without them we'd build a marker at (0,0) and silently
				// mis-complete, so degrade to manual instead.
				if (o.get("x") == null || o.get("y") == null)
				{
					log.warn("Gustav's Helper: position condition missing x/y in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				WorldPoint target = new WorldPoint(getInt(o, "x", 0), getInt(o, "y", 0), getInt(o, "z", 0));
				return new PositionCondition(target, getInt(o, "radius", 8));
			}
			case "and":
				return new AndCondition(parseList(o, stepId));
			case "or":
				return new OrCondition(parseList(o, stepId));
			case "not":
				return new NotCondition(parseSingle(o, stepId));
			default:
				log.warn("Gustav's Helper: unknown condition op '{}' in step '{}'", op, stepId);
				return ConstantCondition.MANUAL;
		}
	}

	private static List<Condition> parseList(JsonObject o, String stepId)
	{
		JsonElement of = o.get("of");
		List<Condition> out = new ArrayList<>();
		if (of != null && of.isJsonArray())
		{
			for (JsonElement e : of.getAsJsonArray())
			{
				out.add(parseNode(e, stepId));
			}
		}
		else if (of != null && of.isJsonObject())
		{
			out.add(parseNode(of, stepId));
		}
		if (out.isEmpty())
		{
			throw new IllegalArgumentException("and/or with empty 'of'");
		}
		return out;
	}

	private static Condition parseSingle(JsonObject o, String stepId)
	{
		JsonElement of = o.get("of");
		if (of == null)
		{
			throw new IllegalArgumentException("not without 'of'");
		}
		if (of.isJsonArray())
		{
			JsonArray arr = of.getAsJsonArray();
			if (arr.size() != 1)
			{
				throw new IllegalArgumentException("not expects a single condition");
			}
			return parseNode(arr.get(0), stepId);
		}
		return parseNode(of, stepId);
	}

	private static QuestState parseQuestState(String s)
	{
		switch (s.trim().toUpperCase())
		{
			case "NOT_STARTED":
			case "NOTSTARTED":
				return QuestState.NOT_STARTED;
			case "IN_PROGRESS":
			case "INPROGRESS":
			case "STARTED":
				return QuestState.IN_PROGRESS;
			case "FINISHED":
			case "COMPLETE":
			case "COMPLETED":
			case "DONE":
			default:
				return QuestState.FINISHED;
		}
	}

	private static String getString(JsonObject o, String key, String def)
	{
		JsonElement e = o.get(key);
		return (e != null && e.isJsonPrimitive()) ? e.getAsString() : def;
	}

	private static int getInt(JsonObject o, String key, int def)
	{
		JsonElement e = o.get(key);
		return (e != null && e.isJsonPrimitive()) ? e.getAsInt() : def;
	}
}
