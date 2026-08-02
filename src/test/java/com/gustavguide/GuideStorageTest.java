/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.gson.Gson;
import com.gustavguide.engine.ConditionContext;
import com.gustavguide.engine.Progression;
import com.gustavguide.engine.Route;
import com.gustavguide.engine.RouteLoader;
import com.gustavguide.engine.RouteStep;
import java.util.HashMap;
import java.util.Map;
import org.junit.Test;
import net.runelite.api.Client;
import net.runelite.client.config.ConfigManager;

/**
 * End-to-end check of the save/load format against a REAL bundled guide: progress and explicitly-undone
 * (suppressed) steps must survive a full write→read cycle through {@link GuideStorage}, so an Undo still
 * holds after a relog. Also pins backward compatibility with saves written before undo existed.
 */
public class GuideStorageTest
{
	private static final String GUIDE = "osiris-ironman";
	private static final String ACCOUNT = "acc_test";

	/** A ConfigManager whose get/set actually round-trip through a map, like the real store. */
	private static ConfigManager fakeStore(Map<String, String> backing)
	{
		ConfigManager cm = mock(ConfigManager.class);
		doAnswer(inv ->
		{
			// Type the value as Object explicitly, or String.valueOf resolves to the char[] overload.
			Object value = inv.getArgument(2);
			return backing.put(inv.getArgument(1), String.valueOf(value));
		}).when(cm).setConfiguration(anyString(), anyString(), any());
		when(cm.getConfiguration(anyString(), anyString()))
			.thenAnswer(inv -> backing.get(inv.<String>getArgument(1)));
		return cm;
	}

	private static ConditionContext freshAccount()
	{
		Client client = mock(Client.class);
		when(client.getRealSkillLevel(any())).thenReturn(1);
		when(client.getVarbitValue(anyInt())).thenReturn(0);
		when(client.getVarpValue(anyInt())).thenReturn(0);
		return new ConditionContext(client);
	}

	@Test
	public void undoSurvivesASaveLoadCycleOnARealGuide()
	{
		Map<String, String> backing = new HashMap<>();
		GuideStorage storage = new GuideStorage(fakeStore(backing));
		Route route = RouteLoader.load(new Gson(), GUIDE);

		// Play forward a few manual steps, then take one back.
		Progression p = new Progression(route, IronmanMode.UIM);
		String first = p.getCurrentStep().getId();
		p.markComplete(first);
		String second = p.getCurrentStep().getId();
		p.markComplete(second);
		assertTrue(p.stepBack());
		assertFalse("the undone step is open again", p.isComplete(second));
		assertTrue("earlier progress is untouched", p.isComplete(first));

		storage.saveProgress(GUIDE, ACCOUNT, p);

		// Relog: a brand-new Progression loaded from the store must remember BOTH sides.
		Progression reloaded = new Progression(route, IronmanMode.UIM);
		storage.loadProgress(GUIDE, ACCOUNT, reloaded);
		assertTrue(reloaded.isComplete(first));
		assertFalse(reloaded.isComplete(second));
		assertTrue(reloaded.getSuppressedIds().contains(second));
		assertEquals("resumes on the step you undid", second, reloaded.getCurrentStep().getId());

		// And the evaluator must not quietly put it back.
		reloaded.process(freshAccount());
		reloaded.foldManualBehindMilestones();
		assertFalse("undo still holds after a relog + evaluation", reloaded.isComplete(second));
	}

	@Test
	public void savedValueKeepsCompletedAndUndoneSeparate()
	{
		Map<String, String> backing = new HashMap<>();
		GuideStorage storage = new GuideStorage(fakeStore(backing));
		Route route = RouteLoader.load(new Gson(), GUIDE);
		Progression p = new Progression(route, IronmanMode.UIM);
		String first = p.getCurrentStep().getId();
		p.markComplete(first);
		p.markComplete(p.getCurrentStep().getId());
		p.stepBack();
		storage.saveProgress(GUIDE, ACCOUNT, p);

		String saved = backing.get("progress_" + GUIDE + "_" + ACCOUNT);
		assertTrue("completed id stored plain", saved.contains(first));
		assertTrue("undone id stored with the marker", saved.contains("!"));
	}

	@Test
	public void aSaveWrittenBeforeUndoExistedStillLoads()
	{
		// Backward compatibility: no "!" entries at all -> everything is completed, nothing suppressed.
		Map<String, String> backing = new HashMap<>();
		Route route = RouteLoader.load(new Gson(), GUIDE);
		RouteStep s0 = route.getSteps().get(0);
		RouteStep s1 = route.getSteps().get(1);
		backing.put("progress_" + GUIDE + "_" + ACCOUNT, s0.getId() + "," + s1.getId());

		Progression p = new Progression(route, IronmanMode.UIM);
		new GuideStorage(fakeStore(backing)).loadProgress(GUIDE, ACCOUNT, p);
		assertTrue(p.isComplete(s0.getId()));
		assertTrue(p.isComplete(s1.getId()));
		assertTrue(p.getSuppressedIds().isEmpty());
	}

	@Test
	public void anEmptySaveLoadsCleanly()
	{
		Map<String, String> backing = new HashMap<>();
		Progression p = new Progression(RouteLoader.load(new Gson(), GUIDE), IronmanMode.UIM);
		new GuideStorage(fakeStore(backing)).loadProgress(GUIDE, ACCOUNT, p);
		assertEquals(0, p.completedCount());
		assertTrue(p.getSuppressedIds().isEmpty());
	}
}
