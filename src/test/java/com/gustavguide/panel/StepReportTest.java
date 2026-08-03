/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.panel;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.gustavguide.engine.RouteStep;
import com.gustavguide.engine.condition.ConstantCondition;
import java.util.Collections;
import org.junit.Test;
import net.runelite.api.coords.WorldPoint;

/**
 * A step report must carry the WHAT and WHERE automatically (so a bad coordinate/highlight is fixable
 * from the report alone), must never carry account information, and must be safe to hand to Discord.
 */
public class StepReportTest
{
	private static RouteStep step()
	{
		return new RouteStep("making-the-loop-around-f-022a", "Making the loop", "Speak with Wilough",
			"Speak with Wilough in the north-east section of the square", null,
			new WorldPoint(3220, 3435, 0), 3503, -1, -1, true,
			Collections.emptySet(), Collections.emptyList(), ConstantCondition.MANUAL);
	}

	@Test
	public void carriesWhatAndWhere()
	{
		String body = StepReport.body("uim-prifddinas", "UIM Walkthrough", step(), 42, 960,
			"points at Gertrude's house instead of Wilough", "1.2.3");
		assertTrue("guide id", body.contains("uim-prifddinas"));
		assertTrue("step id", body.contains("making-the-loop-around-f-022a"));
		assertTrue("step number/total", body.contains("42/960"));
		assertTrue("step text", body.contains("Speak with Wilough in the north-east"));
		assertTrue("the tile it pointed at", body.contains("3220, 3435, plane 0"));
		assertTrue("the npc it highlighted", body.contains("3503"));
		assertTrue("what the user typed", body.contains("points at Gertrude's house"));
		assertTrue("plugin version", body.contains("1.2.3"));
	}

	@Test
	public void saysSoWhenTheUserTypedNothing()
	{
		String body = StepReport.body("g", "G", step(), 1, 2, "   ", "1.0");
		assertTrue(body.contains("(not described)"));
	}

	@Test
	public void survivesANullStepAndNullFields()
	{
		String body = StepReport.body(null, null, null, 0, 0, null, null);
		assertTrue(body.contains("(no current step)"));
		assertFalse(body.isEmpty());
	}

	@Test
	public void whatIsPreviewedIsExactlyWhatIsSent()
	{
		// The panel previews details(...) and sends withProblem(previewed, typed) — the sent body must be
		// the previewed text plus the note, never a rebuild (a rebuild could pick up a different step if
		// the route advanced while the dialog was open).
		String previewed = StepReport.details("uim-prifddinas", "UIM", step(), 42, 960, "1.0");
		String sent = StepReport.withProblem(previewed, "wrong npc");
		assertTrue("the previewed text is carried verbatim", sent.startsWith(previewed));
		assertTrue(sent.contains("**Problem:** wrong npc"));
		assertFalse("details alone carries no problem line", previewed.contains("**Problem:**"));
	}

	@Test
	public void aVeryLongStepCannotOverflowDiscordsLimit()
	{
		StringBuilder huge = new StringBuilder();
		for (int i = 0; i < 500; i++)
		{
			huge.append("some very long step text that repeats. ");
		}
		RouteStep big = new RouteStep("x-001", "S", "t", huge.toString(), null,
			null, -1, -1, -1, true, Collections.emptySet(), Collections.emptyList(), ConstantCondition.MANUAL);
		String body = StepReport.body("g", "G", big, 1, 1, huge.toString(), "1.0");
		// Discord's 2000-char cap applies to the DECODED content, not the escaped JSON payload.
		assertTrue("content stays under Discord's 2000-char message cap, was " + body.length(),
			body.length() <= 1801);
		assertTrue(StepReport.discordPayload(body).startsWith("{\"content\":"));
	}

	@Test
	public void payloadIsValidJsonAndCannotPingAnyone()
	{
		String payload = StepReport.discordPayload("a \"quoted\" line\nwith a newline \\ and @everyone");
		assertTrue(payload.startsWith("{\"content\":\""));
		assertTrue("quotes escaped", payload.contains("\\\"quoted\\\""));
		assertTrue("newline escaped", payload.contains("\\n"));
		assertTrue("backslash escaped", payload.contains("\\\\"));
		assertTrue("mentions disabled so a report can never ping a role",
			payload.contains("\"allowed_mentions\":{\"parse\":[]}"));
	}

	@Test
	public void carriesNoAccountInformation()
	{
		// The report is built only from guide data + what the user typed. Nothing identifies the account:
		// no player name, no account hash, no player position.
		String body = StepReport.body("uim-prifddinas", "UIM", step(), 3, 10, "wrong npc", "1.0");
		for (String forbidden : new String[]{"acc_", "accountHash", "username", "playerName", "rsn"})
		{
			assertFalse("must not leak " + forbidden, body.toLowerCase().contains(forbidden.toLowerCase()));
		}
	}

	@Test
	public void jsonEscapingHandlesControlCharacters()
	{
		assertEquals("\"a\\u0007b\"", StepReport.jsonString("ab"));
	}
}
