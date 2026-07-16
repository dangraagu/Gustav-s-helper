/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide;

import com.osirisguide.engine.Progression;
import com.osirisguide.engine.ledger.ItemLedger;
import java.util.Arrays;
import java.util.Collections;
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
		String value = String.join(",", progression.getCompletedIds());
		configManager.setConfiguration(OsirisGuideConfig.GROUP, progressKey(guideId, accountKey), value);
	}

	/** Load the completed-step ids into {@code progression} (empty if nothing saved). */
	void loadProgress(String guideId, String accountKey, Progression progression)
	{
		String value = configManager.getConfiguration(OsirisGuideConfig.GROUP, progressKey(guideId, accountKey));
		if (value == null || value.isEmpty())
		{
			progression.setCompletedIds(Collections.emptyList());
			return;
		}
		progression.setCompletedIds(Arrays.asList(value.split(",")));
	}

	/** Persist the ledger's acquired totals (display history). */
	void saveLedger(String guideId, String accountKey, ItemLedger ledger)
	{
		configManager.setConfiguration(OsirisGuideConfig.GROUP, ledgerKey(guideId, accountKey),
			ledger.acquiredToString());
	}

	/**
	 * Load the ledger's acquired totals, then drop live snapshots so owned/spent re-seed against this
	 * login's fresh containers.
	 */
	void loadLedger(String guideId, String accountKey, ItemLedger ledger)
	{
		String value = configManager.getConfiguration(OsirisGuideConfig.GROUP, ledgerKey(guideId, accountKey));
		ledger.acquiredFromString(value);
		ledger.clearSnapshots();
	}

	// Birdhouse-run reminder state is per ACCOUNT (not per guide): the run cycle is a property of the
	// account's real birdhouses, whichever guide is selected.

	private static String birdhouseKey(String accountKey)
	{
		return "birdhouse_last_" + accountKey;
	}

	void saveBirdhouseVisit(String accountKey, long lastVisitMs)
	{
		configManager.setConfiguration(OsirisGuideConfig.GROUP, birdhouseKey(accountKey), Long.toString(lastVisitMs));
	}

	long loadBirdhouseVisit(String accountKey)
	{
		String value = configManager.getConfiguration(OsirisGuideConfig.GROUP, birdhouseKey(accountKey));
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
