/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide;

import com.gustavguide.engine.Progression;
import com.gustavguide.engine.ledger.ItemLedger;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import net.runelite.client.config.ConfigManager;

/**
 * Reads and writes a guide's saved state (completed-step ids + item-ledger totals) in the RuneLite
 * config store. Every key is scoped by BOTH guide id and account key, so switching guide or account
 * never mixes one save into another's slot. This class is the single source of the key format.
 *
 * <p>Callers guard on progression/ledger/account being present; this class assumes valid arguments
 * and only performs the store read/write + (de)serialisation.</p>
 */
class GuideStorage
{
	private final ConfigManager configManager;

	GuideStorage(ConfigManager configManager)
	{
		this.configManager = configManager;
	}

	/** Marks an explicitly-undone step id inside the saved progress value (see saveProgress). */
	private static final char SUPPRESSED_PREFIX = '!';

	private static String progressKey(String guideId, String accountKey)
	{
		return "progress_" + guideId + "_" + accountKey;
	}

	private static String ledgerKey(String guideId, String accountKey)
	{
		return "ledger_" + guideId + "_" + accountKey;
	}

	/** Persist the completed-step ids as a comma-joined list. */
	void saveProgress(String guideId, String accountKey, Progression progression)
	{
		// Completed ids plain; explicitly-undone (suppressed) ids carry a "!" prefix in the SAME value.
		// Backward compatible: values written before undo existed simply have no "!" entries.
		StringBuilder sb = new StringBuilder(String.join(",", progression.getCompletedIds()));
		for (String id : progression.getSuppressedIds())
		{
			if (sb.length() > 0)
			{
				sb.append(',');
			}
			sb.append(SUPPRESSED_PREFIX).append(id);
		}
		configManager.setConfiguration(GustavGuideConfig.GROUP, progressKey(guideId, accountKey), sb.toString());
	}

	/** Load the completed-step ids into {@code progression} (empty if nothing saved). */
	void loadProgress(String guideId, String accountKey, Progression progression)
	{
		String value = configManager.getConfiguration(GustavGuideConfig.GROUP, progressKey(guideId, accountKey));
		if (value == null || value.isEmpty())
		{
			progression.setCompletedIds(Collections.emptyList());
			progression.setSuppressedIds(Collections.emptyList());
			return;
		}
		List<String> done = new ArrayList<>();
		List<String> undone = new ArrayList<>();
		for (String part : value.split(","))
		{
			if (part.isEmpty())
			{
				continue;
			}
			if (part.charAt(0) == SUPPRESSED_PREFIX)
			{
				undone.add(part.substring(1));
			}
			else
			{
				done.add(part);
			}
		}
		progression.setCompletedIds(done);
		progression.setSuppressedIds(undone);
	}

	/** Persist the ledger's acquired totals (display history). */
	void saveLedger(String guideId, String accountKey, ItemLedger ledger)
	{
		configManager.setConfiguration(GustavGuideConfig.GROUP, ledgerKey(guideId, accountKey),
			ledger.acquiredToString());
	}

	/**
	 * Load the ledger's acquired totals, then drop live snapshots so owned/spent re-seed against this
	 * login's fresh containers.
	 */
	void loadLedger(String guideId, String accountKey, ItemLedger ledger)
	{
		String value = configManager.getConfiguration(GustavGuideConfig.GROUP, ledgerKey(guideId, accountKey));
		ledger.acquiredFromString(value);
		ledger.clearSnapshots();
	}

	// Per-step user notes. One config value per guide+account; step ids never contain '=' or ',' and
	// the note text is URL-encoded, so "id=encoded,id=encoded" round-trips any text the user types.

	private static String notesKey(String guideId, String accountKey)
	{
		return "notes_" + guideId + "_" + accountKey;
	}

	void saveNote(String guideId, String accountKey, String stepId, String note)
	{
		java.util.Map<String, String> notes = loadNotes(guideId, accountKey);
		if (note == null || note.trim().isEmpty())
		{
			notes.remove(stepId);
		}
		else
		{
			notes.put(stepId, note.trim());
		}
		StringBuilder sb = new StringBuilder();
		for (java.util.Map.Entry<String, String> e : notes.entrySet())
		{
			if (sb.length() > 0)
			{
				sb.append(',');
			}
			try
			{
				sb.append(e.getKey()).append('=')
					.append(java.net.URLEncoder.encode(e.getValue(), "UTF-8"));
			}
			catch (java.io.UnsupportedEncodingException impossible)
			{
				// UTF-8 is guaranteed by the JVM spec.
			}
		}
		configManager.setConfiguration(GustavGuideConfig.GROUP, notesKey(guideId, accountKey), sb.toString());
	}

	java.util.Map<String, String> loadNotes(String guideId, String accountKey)
	{
		java.util.Map<String, String> out = new java.util.LinkedHashMap<>();
		String value = configManager.getConfiguration(GustavGuideConfig.GROUP, notesKey(guideId, accountKey));
		if (value == null || value.isEmpty())
		{
			return out;
		}
		for (String part : value.split(","))
		{
			int eq = part.indexOf('=');
			if (eq <= 0)
			{
				continue;
			}
			try
			{
				out.put(part.substring(0, eq), java.net.URLDecoder.decode(part.substring(eq + 1), "UTF-8"));
			}
			catch (Exception ignored)
			{
				// a malformed entry loses only itself, never the whole map
			}
		}
		return out;
	}

	// Birdhouse-run reminder state is per ACCOUNT (not per guide): the run cycle is a property of the
	// account's real birdhouses, whichever guide is selected.

	private static String birdhouseKey(String accountKey)
	{
		return "birdhouse_last_" + accountKey;
	}

	void saveBirdhouseVisit(String accountKey, long lastVisitMs)
	{
		configManager.setConfiguration(GustavGuideConfig.GROUP, birdhouseKey(accountKey), Long.toString(lastVisitMs));
	}

	long loadBirdhouseVisit(String accountKey)
	{
		String value = configManager.getConfiguration(GustavGuideConfig.GROUP, birdhouseKey(accountKey));
		if (value == null || value.isEmpty())
		{
			return 0L;
		}
		try
		{
			return Long.parseLong(value.trim());
		}
		catch (NumberFormatException ignored)
		{
			return 0L;
		}
	}
}
