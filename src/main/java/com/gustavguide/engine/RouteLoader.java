/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.gustavguide.IronmanMode;
import com.gustavguide.engine.condition.Condition;
import com.gustavguide.engine.condition.ConstantCondition;
import com.gustavguide.engine.condition.QuestCondition;
import com.gustavguide.requirement.ItemRequirement;
import com.gustavguide.requirement.QuestRequirement;
import com.gustavguide.requirement.Requirement;
import com.gustavguide.requirement.SkillRequirement;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;

/**
 * Loads the route from bundled JSON resources. Structure:
 * <pre>
 *   /com/gustavguide/data/route/route-index.json   -> { "sections": ["01-early-game.json", ...] }
 *   /com/gustavguide/data/route/01-early-game.json  -> { "section": "Early Game", "steps": [ ... ] }
 * </pre>
 * Section files are concatenated in index order; steps keep their in-file order.
 */
@Slf4j
public final class RouteLoader
{
	private static final String BASE = "/com/gustavguide/data/guides/";

	private RouteLoader()
	{
	}

	// ---- DTOs (Gson) --------------------------------------------------------

	static final class IndexDto
	{
		List<String> sections;
	}

	static final class SectionDto
	{
		String section;
		List<StepDto> steps;
	}

	static final class StepDto
	{
		String id;
		String title;
		String text;
		String wiki;
		String note;           // optional panel tip (skill-training method, etc.)
		String quest;          // convenience: default complete = this quest FINISHED
		int[] world;           // [x, y, plane]
		Integer npc;           // highlight npc id
		int[] npcs;            // several acceptable npc ids ("talk to any man"); wins over npc
		Integer object;        // highlight object id
		Integer item;          // highlight inventory item id
		Boolean manual;
		List<String> modes;
		List<RequirementDto> requirements;
		JsonElement complete;  // raw condition tree
	}

	static final class RequirementDto
	{
		String type;   // skill | item | quest
		String skill;
		Integer level;
		Integer id;
		Integer qty;
		String name;
		String scope;
		String quest;
		String state;
	}

	// ---- Public API ---------------------------------------------------------

	/** Loads the bundled route for the given guide id (folder under {@code data/guides/<id>/}). */
	public static Route load(Gson gson, String guideId)
	{
		String base = BASE + guideId + "/";
		IndexDto index = readResource(gson, base + "route-index.json", IndexDto.class);
		if (index == null || index.sections == null || index.sections.isEmpty())
		{
			log.warn("Gustav's Helper: route index missing or empty for guide '{}'; no route loaded", guideId);
			return new Route(new ArrayList<>());
		}
		List<RouteStep> steps = new ArrayList<>();
		Set<String> seen = new HashSet<>();
		for (String file : index.sections)
		{
			SectionDto section = readResource(gson, base + file, SectionDto.class);
			if (section == null || section.steps == null)
			{
				log.warn("Gustav's Helper: section file '{}' missing or empty", file);
				continue;
			}
			for (StepDto dto : section.steps)
			{
				addUnique(steps, seen, convert(dto, section.section));
			}
		}
		log.debug("Gustav's Helper: guide '{}' loaded {} steps across {} sections",
			guideId, steps.size(), index.sections.size());
		return new Route(steps);
	}

	/** Test/utility entry point: build a route from already-parsed section JSON strings. */
	public static Route fromSectionJson(Gson gson, List<String> sectionJson)
	{
		List<RouteStep> steps = new ArrayList<>();
		Set<String> seen = new HashSet<>();
		for (String json : sectionJson)
		{
			SectionDto section = gson.fromJson(json, SectionDto.class);
			if (section == null || section.steps == null)
			{
				continue;
			}
			for (StepDto dto : section.steps)
			{
				addUnique(steps, seen, convert(dto, section.section));
			}
		}
		return new Route(steps);
	}

	// ---- Conversion ---------------------------------------------------------

	private static void addUnique(List<RouteStep> steps, Set<String> seen, RouteStep step)
	{
		if (step == null)
		{
			return;
		}
		if (!seen.add(step.getId()))
		{
			log.warn("Gustav's Helper: duplicate step id '{}' ignored", step.getId());
			return;
		}
		steps.add(step);
	}

	private static RouteStep convert(StepDto dto, String section)
	{
		if (dto == null || dto.id == null || dto.id.isEmpty())
		{
			log.warn("Gustav's Helper: skipping step with missing id in section '{}'", section);
			return null;
		}
		boolean manual = dto.manual != null && dto.manual;
		Condition complete = resolveComplete(dto, manual);

		WorldPoint wp = null;
		if (dto.world != null && dto.world.length >= 2)
		{
			int plane = dto.world.length >= 3 ? dto.world[2] : 0;
			wp = new WorldPoint(dto.world[0], dto.world[1], plane);
		}

		Set<IronmanMode> modes = parseModes(dto.modes, dto.id);
		List<Requirement> reqs = parseRequirements(dto.requirements, dto.id);

		List<Integer> npcIds = new ArrayList<>();
		if (dto.npcs != null && dto.npcs.length > 0)
		{
			for (int id : dto.npcs)
			{
				if (id >= 0)
				{
					npcIds.add(id);
				}
			}
		}
		else if (dto.npc != null && dto.npc >= 0)
		{
			npcIds.add(dto.npc);
		}

		return new RouteStep(
			dto.id,
			section,
			dto.title != null ? dto.title : dto.id,
			dto.text != null ? dto.text : "",
			dto.wiki,
			wp,
			npcIds,
			dto.object != null ? dto.object : -1,
			dto.item != null ? dto.item : -1,
			manual,
			modes,
			reqs,
			complete,
			dto.note);
	}

	private static Condition resolveComplete(StepDto dto, boolean manual)
	{
		if (dto.complete != null && !dto.complete.isJsonNull())
		{
			return ConditionFactory.parse(dto.complete, dto.id);
		}
		if (manual)
		{
			return ConstantCondition.MANUAL;
		}
		// Convenience: a step that names a quest and gives no explicit condition auto-completes
		// when that quest is FINISHED.
		if (dto.quest != null && !dto.quest.isEmpty())
		{
			try
			{
				return new QuestCondition(Quest.valueOf(dto.quest.toUpperCase()), QuestState.FINISHED);
			}
			catch (IllegalArgumentException e)
			{
				log.warn("Gustav's Helper: unknown quest '{}' in step '{}'", dto.quest, dto.id);
			}
		}
		return ConstantCondition.MANUAL;
	}

	private static Set<IronmanMode> parseModes(List<String> modeStrings, String stepId)
	{
		Set<IronmanMode> modes = EnumSet.noneOf(IronmanMode.class);
		if (modeStrings == null)
		{
			return modes;
		}
		for (String m : modeStrings)
		{
			try
			{
				modes.add(IronmanMode.valueOf(m.trim().toUpperCase()));
			}
			catch (IllegalArgumentException e)
			{
				log.warn("Gustav's Helper: unknown mode '{}' in step '{}'", m, stepId);
			}
		}
		return modes;
	}

	private static List<Requirement> parseRequirements(List<RequirementDto> dtos, String stepId)
	{
		List<Requirement> out = new ArrayList<>();
		if (dtos == null)
		{
			return out;
		}
		for (RequirementDto r : dtos)
		{
			Requirement req = toRequirement(r, stepId);
			if (req != null)
			{
				out.add(req);
			}
		}
		return out;
	}

	private static Requirement toRequirement(RequirementDto r, String stepId)
	{
		if (r == null || r.type == null)
		{
			return null;
		}
		try
		{
			switch (r.type.toLowerCase())
			{
				case "skill":
					return new SkillRequirement(Skill.valueOf(r.skill.toUpperCase()),
						r.level != null ? r.level : 1);
				case "item":
					return new ItemRequirement(r.id != null ? r.id : -1,
						r.qty != null ? r.qty : 1, r.name,
						ItemScope.fromString(r.scope != null ? r.scope : "ANY"));
				case "quest":
					return new QuestRequirement(Quest.valueOf(r.quest.toUpperCase()),
						r.state != null ? QuestState.valueOf(r.state.toUpperCase()) : QuestState.FINISHED);
				default:
					log.warn("Gustav's Helper: unknown requirement type '{}' in step '{}'", r.type, stepId);
					return null;
			}
		}
		catch (IllegalArgumentException | NullPointerException e)
		{
			log.warn("Gustav's Helper: bad requirement in step '{}': {}", stepId, e.getMessage());
			return null;
		}
	}

	private static <T> T readResource(Gson gson, String path, Class<T> type)
	{
		try (InputStream in = RouteLoader.class.getResourceAsStream(path))
		{
			if (in == null)
			{
				return null;
			}
			try (Reader reader = new InputStreamReader(in, StandardCharsets.UTF_8))
			{
				return gson.fromJson(reader, type);
			}
		}
		catch (Exception e)
		{
			log.warn("Gustav's Helper: failed to read resource '{}': {}", path, e.getMessage());
			return null;
		}
	}
}
