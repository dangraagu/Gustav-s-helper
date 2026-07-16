/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Quest;

/**
 * Expected NPC-dialogue options, harvested at build time from Quest Helper's source (see NOTICE) into
 * {@code data/qh_dialogue.json}. Pure reference data — no runtime Quest-Helper dependency.
 *
 * <p>Given the current step's quest (and its text), {@link #expectedNormalized} returns the set of
 * option strings Quest Helper would tell the player to click, normalised for matching. The overlay
 * highlights a live dialogue option only when its normalised text is in that set — so a wrong option
 * is never highlighted, and steps with no known options get no highlight.</p>
 */
@Slf4j
public class DialogueDb
{
	/** RuneLite Quest constant name -> option strings QH clicks during that quest. */
	private final Map<String, List<String>> byQuest;
	/** NPC name -> option strings, for non-quest talk steps. Keys can carry gameval suffixes. */
	private final Map<String, List<String>> byNpc;

	DialogueDb(Map<String, List<String>> byQuest, Map<String, List<String>> byNpc)
	{
		this.byQuest = byQuest == null ? Collections.emptyMap() : byQuest;
		this.byNpc = byNpc == null ? Collections.emptyMap() : byNpc;
	}

	/** Loads the bundled dialogue DB; returns an empty DB (never null) if it's missing/unreadable. */
	public static DialogueDb load(Gson gson)
	{
		try (InputStream in = DialogueDb.class.getResourceAsStream("/com/osirisguide/data/qh_dialogue.json"))
		{
			if (in == null)
			{
				log.warn("Gustav's Helper: qh_dialogue.json not found on the classpath");
				return new DialogueDb(null, null);
			}
			Model m = gson.fromJson(new InputStreamReader(in, StandardCharsets.UTF_8), Model.class);
			return m == null ? new DialogueDb(null, null) : new DialogueDb(m.byQuest, m.byNpc);
		}
		catch (Exception e) // noqa: broad — a bad data file must never break plugin start-up
		{
			log.warn("Gustav's Helper: could not load qh_dialogue.json: {}", e.getMessage());
			return new DialogueDb(null, null);
		}
	}

	private static final class Model
	{
		@SerializedName("byQuest")
		Map<String, List<String>> byQuest;
		@SerializedName("byNpc")
		Map<String, List<String>> byNpc;
	}

	public boolean isEmpty()
	{
		return byQuest.isEmpty() && byNpc.isEmpty();
	}

	/**
	 * The normalised option strings expected for the current step: everything for its quest, plus any
	 * NPC whose name appears in the step text (covers non-quest talk steps).
	 *
	 * @param quest    the step's quest, or null if it isn't a quest step
	 * @param stepText the step's text (used to spot a named NPC), may be null
	 */
	public Set<String> expectedNormalized(Quest quest, String stepText)
	{
		Set<String> out = new HashSet<>();
		if (quest != null)
		{
			addNormalized(out, byQuest.get(quest.name()));
		}
		if (stepText != null && !byNpc.isEmpty())
		{
			String haystack = stepText.toLowerCase();
			for (Map.Entry<String, List<String>> e : byNpc.entrySet())
			{
				String first = firstToken(e.getKey());
				// require a 4+ char first token so short/common names don't over-match the step text
				if (first.length() >= 4 && haystack.contains(first))
				{
					addNormalized(out, e.getValue());
				}
			}
		}
		return out;
	}

	private static void addNormalized(Set<String> out, List<String> options)
	{
		if (options == null)
		{
			return;
		}
		for (String o : options)
		{
			String n = normalize(o);
			if (!n.isEmpty())
			{
				out.add(n);
			}
		}
	}

	private static String firstToken(String key)
	{
		if (key == null)
		{
			return "";
		}
		String k = key.trim().toLowerCase();
		int sp = k.indexOf(' ');
		return sp < 0 ? k : k.substring(0, sp);
	}

	/**
	 * Canonical form for comparing a live widget option against a stored one: strip widget colour/markup
	 * tags, lower-case, drop punctuation, and collapse whitespace. So {@code "<col=00ff00>Yes.</col>"}
	 * and {@code "Yes"} both become {@code "yes"}.
	 */
	public static String normalize(String s)
	{
		if (s == null)
		{
			return "";
		}
		String t = s.replaceAll("<[^>]*>", " ");   // widget markup tags
		t = t.toLowerCase();
		t = t.replace("'", "").replace("’", ""); // apostrophes join the word: "what's" -> "whats"
		t = t.replaceAll("[^a-z0-9 ]", " ");        // other punctuation -> space (incl. QH's trailing '.')
		t = t.trim().replaceAll("\\s+", " ");
		return t;
	}
}
