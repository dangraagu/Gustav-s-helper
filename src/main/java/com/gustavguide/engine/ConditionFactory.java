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
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;
import net.runelite.api.Skill;
import net.runelite.api.Varbits;
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
	/** Default arrival radius (tiles) for a position condition when the data omits an explicit one. */
	private static final int DEFAULT_POSITION_RADIUS = 8;

	/** Achievement-diary completion varbits (>= 1 when that tier is complete), keyed "area|tier".
	 *  Lets a diary step auto-sync at login like a skill/quest. Karamja is intentionally omitted —
	 *  its completion varbits aren't clean 0/1 flags like the other 11 areas. */
	private static final Map<String, Integer> DIARY_VARBITS = new HashMap<>();

	static
	{
		DIARY_VARBITS.put("ardougne|easy", Varbits.DIARY_ARDOUGNE_EASY);
		DIARY_VARBITS.put("ardougne|medium", Varbits.DIARY_ARDOUGNE_MEDIUM);
		DIARY_VARBITS.put("ardougne|hard", Varbits.DIARY_ARDOUGNE_HARD);
		DIARY_VARBITS.put("ardougne|elite", Varbits.DIARY_ARDOUGNE_ELITE);
		DIARY_VARBITS.put("desert|easy", Varbits.DIARY_DESERT_EASY);
		DIARY_VARBITS.put("desert|medium", Varbits.DIARY_DESERT_MEDIUM);
		DIARY_VARBITS.put("desert|hard", Varbits.DIARY_DESERT_HARD);
		DIARY_VARBITS.put("desert|elite", Varbits.DIARY_DESERT_ELITE);
		DIARY_VARBITS.put("falador|easy", Varbits.DIARY_FALADOR_EASY);
		DIARY_VARBITS.put("falador|medium", Varbits.DIARY_FALADOR_MEDIUM);
		DIARY_VARBITS.put("falador|hard", Varbits.DIARY_FALADOR_HARD);
		DIARY_VARBITS.put("falador|elite", Varbits.DIARY_FALADOR_ELITE);
		DIARY_VARBITS.put("fremennik|easy", Varbits.DIARY_FREMENNIK_EASY);
		DIARY_VARBITS.put("fremennik|medium", Varbits.DIARY_FREMENNIK_MEDIUM);
		DIARY_VARBITS.put("fremennik|hard", Varbits.DIARY_FREMENNIK_HARD);
		DIARY_VARBITS.put("fremennik|elite", Varbits.DIARY_FREMENNIK_ELITE);
		DIARY_VARBITS.put("kandarin|easy", Varbits.DIARY_KANDARIN_EASY);
		DIARY_VARBITS.put("kandarin|medium", Varbits.DIARY_KANDARIN_MEDIUM);
		DIARY_VARBITS.put("kandarin|hard", Varbits.DIARY_KANDARIN_HARD);
		DIARY_VARBITS.put("kandarin|elite", Varbits.DIARY_KANDARIN_ELITE);
		DIARY_VARBITS.put("kourend|easy", Varbits.DIARY_KOUREND_EASY);
		DIARY_VARBITS.put("kourend|medium", Varbits.DIARY_KOUREND_MEDIUM);
		DIARY_VARBITS.put("kourend|hard", Varbits.DIARY_KOUREND_HARD);
		DIARY_VARBITS.put("kourend|elite", Varbits.DIARY_KOUREND_ELITE);
		DIARY_VARBITS.put("lumbridge|easy", Varbits.DIARY_LUMBRIDGE_EASY);
		DIARY_VARBITS.put("lumbridge|medium", Varbits.DIARY_LUMBRIDGE_MEDIUM);
		DIARY_VARBITS.put("lumbridge|hard", Varbits.DIARY_LUMBRIDGE_HARD);
		DIARY_VARBITS.put("lumbridge|elite", Varbits.DIARY_LUMBRIDGE_ELITE);
		DIARY_VARBITS.put("morytania|easy", Varbits.DIARY_MORYTANIA_EASY);
		DIARY_VARBITS.put("morytania|medium", Varbits.DIARY_MORYTANIA_MEDIUM);
		DIARY_VARBITS.put("morytania|hard", Varbits.DIARY_MORYTANIA_HARD);
		DIARY_VARBITS.put("morytania|elite", Varbits.DIARY_MORYTANIA_ELITE);
		DIARY_VARBITS.put("varrock|easy", Varbits.DIARY_VARROCK_EASY);
		DIARY_VARBITS.put("varrock|medium", Varbits.DIARY_VARROCK_MEDIUM);
		DIARY_VARBITS.put("varrock|hard", Varbits.DIARY_VARROCK_HARD);
		DIARY_VARBITS.put("varrock|elite", Varbits.DIARY_VARROCK_ELITE);
		DIARY_VARBITS.put("western|easy", Varbits.DIARY_WESTERN_EASY);
		DIARY_VARBITS.put("western|medium", Varbits.DIARY_WESTERN_MEDIUM);
		DIARY_VARBITS.put("western|hard", Varbits.DIARY_WESTERN_HARD);
		DIARY_VARBITS.put("western|elite", Varbits.DIARY_WESTERN_ELITE);
		DIARY_VARBITS.put("wilderness|easy", Varbits.DIARY_WILDERNESS_EASY);
		DIARY_VARBITS.put("wilderness|medium", Varbits.DIARY_WILDERNESS_MEDIUM);
		DIARY_VARBITS.put("wilderness|hard", Varbits.DIARY_WILDERNESS_HARD);
		DIARY_VARBITS.put("wilderness|elite", Varbits.DIARY_WILDERNESS_ELITE);
	}

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
				int id = requireId(o, "itemAcquired", stepId);
				if (id < 0)
				{
					return ConstantCondition.MANUAL;
				}
				return new ItemAcquiredCondition(id, getInt(o, "qty", 1));
			}
			case "itemconsumed":
			case "itemspent":
			case "consumed":
			{
				int id = requireId(o, "itemConsumed", stepId);
				if (id < 0)
				{
					return ConstantCondition.MANUAL;
				}
				return new ItemConsumedCondition(id, getInt(o, "qty", 1));
			}
			case "varbit":
			{
				int id = requireId(o, "varbit", stepId);
				if (id < 0)
				{
					return ConstantCondition.MANUAL;
				}
				return new VarbitCondition(id, getInt(o, "value", 0), Op.fromString(getString(o, "cmp", ">=")));
			}
			case "varp":
			{
				int id = requireId(o, "varp", stepId);
				if (id < 0)
				{
					return ConstantCondition.MANUAL;
				}
				return new VarpCondition(id, getInt(o, "value", 0), Op.fromString(getString(o, "cmp", ">=")));
			}
			case "diary":
			{
				// Achievement-diary completion syncs like a skill/quest: the tier's varbit is >= 1 when done.
				Integer vb = DIARY_VARBITS.get(
					getString(o, "area", "").toLowerCase() + "|" + getString(o, "tier", "").toLowerCase());
				if (vb == null)
				{
					log.warn("Gustav's Helper: unknown diary area/tier in step '{}'", stepId);
					return ConstantCondition.MANUAL;
				}
				return new VarbitCondition(vb, 1, Op.fromString(">="));
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
				return new PositionCondition(target, getInt(o, "radius", DEFAULT_POSITION_RADIUS));
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

	/**
	 * Reads the required {@code "id"} field shared by the item-acquired/consumed and varbit/varp
	 * conditions. Logs a diagnostic and returns -1 (which the caller checks) when it's absent or
	 * negative, so the step degrades to {@link ConstantCondition#MANUAL} rather than building a
	 * condition around a bogus id.
	 *
	 * @param condName human-readable condition name for the diagnostic
	 */
	private static int requireId(JsonObject o, String condName, String stepId)
	{
		int id = getInt(o, "id", -1);
		if (id < 0)
		{
			log.warn("Gustav's Helper: {} condition missing/invalid id in step '{}'", condName, stepId);
		}
		return id;
	}
}
