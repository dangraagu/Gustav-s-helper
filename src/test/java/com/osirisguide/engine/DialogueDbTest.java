/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import net.runelite.api.Quest;
import org.junit.Test;

public class DialogueDbTest
{
	@Test
	public void normalizeStripsTagsPunctuationAndCase()
	{
		assertEquals("yes", DialogueDb.normalize("<col=00ff00>Yes.</col>"));
		assertEquals("yes", DialogueDb.normalize("Yes"));
		assertEquals("whats wrong", DialogueDb.normalize("What's wrong?"));
		assertEquals("i need soft clay", DialogueDb.normalize("I need   soft clay."));
		assertEquals("", DialogueDb.normalize(null));
	}

	@Test
	public void byQuestReturnsThatQuestsOptionsNormalized()
	{
		Map<String, java.util.List<String>> byQuest = new HashMap<>();
		byQuest.put("COOKS_ASSISTANT", Arrays.asList("Yes.", "Can I help?"));
		DialogueDb db = new DialogueDb(byQuest, Collections.emptyMap());

		Set<String> exp = db.expectedNormalized(Quest.COOKS_ASSISTANT, null);
		assertTrue(exp.contains("yes"));
		assertTrue(exp.contains("can i help"));
		// a live option matches by normalised membership
		assertTrue(exp.contains(DialogueDb.normalize("<col=0000ff>Yes</col>")));
		// unrelated quest -> nothing
		assertTrue(db.expectedNormalized(Quest.DRAGON_SLAYER_I, null).isEmpty());
		// no quest, no text -> nothing
		assertTrue(db.expectedNormalized(null, null).isEmpty());
	}

	@Test
	public void byNpcMatchesWhenNameIsInStepText()
	{
		Map<String, java.util.List<String>> byNpc = new HashMap<>();
		byNpc.put("aggie 1op", Collections.singletonList("I need soft clay."));  // gameval-suffixed key
		byNpc.put("cat", Collections.singletonList("Meow"));                      // too-short first token
		DialogueDb db = new DialogueDb(Collections.emptyMap(), byNpc);

		Set<String> hit = db.expectedNormalized(null, "Talk to Aggie in Draynor.");
		assertTrue(hit.contains("i need soft clay"));

		// NPC not named in the text -> no options
		assertFalse(db.expectedNormalized(null, "Talk to Bob.").contains("i need soft clay"));
		// 3-char first token must not match even when present in the text
		assertTrue(db.expectedNormalized(null, "Pet the cat.").isEmpty());
	}

	@Test
	public void loadMissingResourceYieldsEmptyDbNotCrash()
	{
		DialogueDb empty = new DialogueDb(null, null);
		assertTrue(empty.isEmpty());
		assertTrue(empty.expectedNormalized(Quest.COOKS_ASSISTANT, "anything").isEmpty());
	}
}
