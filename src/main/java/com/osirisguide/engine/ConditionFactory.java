/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.osirisguide.engine.condition.AndCondition;
import com.osirisguide.engine.condition.Condition;
import com.osirisguide.engine.condition.ConstantCondition;
import com.osirisguide.engine.condition.ItemAcquiredCondition;
import com.osirisguide.engine.condition.ItemCondition;
import com.osirisguide.engine.condition.ItemConsumedCondition;
import com.osirisguide.engine.condition.NotCondition;
import com.osirisguide.engine.condition.OrCondition;
import com.osirisguide.engine.condition.QuestCondition;
import com.osirisguide.engine.condition.QuestPointsCondition;
import com.osirisguide.engine.condition.SkillCondition;
import com.osirisguide.engine.condition.VarbitCondition;
import com.osirisguide.engine.condition.VarpCondition;
import java.util.ArrayList;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;
import net.runelite.api.Skill;

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
			log.warn("Osiris Guide: could not parse condition for step '{}': {}", stepId, e.getMessage());
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
					log.warn("Osiris Guide: itemAcquired condition missing/invalid id in step '{}'", stepId);
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
					log.warn("Osiris Guide: itemConsumed condition missing/invalid id in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new ItemConsumedCondition(id, getInt(o, "qty", 1));
			}
			case "varbit":
			{
				int id = getInt(o, "id", -1);
				if (id < 0)
				{
					log.warn("Osiris Guide: varbit condition missing/invalid id in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new VarbitCondition(id, getInt(o, "value", 0), Op.fromString(getString(o, "cmp", ">=")));
			}
			case "varp":
			{
				int id = getInt(o, "id", -1);
				if (id < 0)
				{
					log.warn("Osiris Guide: varp condition missing/invalid id in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new VarpCondition(id, getInt(o, "value", 0), Op.fromString(getString(o, "cmp", ">=")));
			}
			case "and":
				return new AndCondition(parseList(o, stepId));
			case "or":
				return new OrCondition(parseList(o, stepId));
			case "not":
				return new NotCondition(parseSingle(o, stepId));
			default:
				log.warn("Osiris Guide: unknown condition op '{}' in step '{}'", op, stepId);
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
