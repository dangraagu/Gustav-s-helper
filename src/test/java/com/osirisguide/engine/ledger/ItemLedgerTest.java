/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.ledger;

import static org.junit.Assert.assertEquals;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import org.junit.Test;

public class ItemLedgerTest
{
	private static final int INV = 93;
	private static final int BANK = 95;
	private static final int COINS = 995;
	private static final int TAR = 1939; // swamp tar

	private static Map<Integer, Integer> counts(Object... pairs)
	{
		Map<Integer, Integer> m = new HashMap<>();
		for (int i = 0; i < pairs.length; i += 2)
		{
			m.put((Integer) pairs[i], (Integer) pairs[i + 1]);
		}
		return m;
	}

	@Test
	public void firstSnapshotSeedsWithoutCounting()
	{
		ItemLedger l = new ItemLedger();
		l.observe(INV, counts(COINS, 100));
		l.commit();
		assertEquals(0, l.acquired(COINS));
		assertEquals(100, l.owned(COINS));
		assertEquals(0, l.spent(COINS));
	}

	@Test
	public void gainsAccrueToAcquired()
	{
		ItemLedger l = new ItemLedger();
		l.observe(INV, counts());
		l.commit();                        // seed
		l.observe(INV, counts(TAR, 5));
		l.commit();                        // +5
		l.observe(INV, counts(TAR, 8));
		l.commit();                        // +3
		assertEquals(8, l.acquired(TAR));
		assertEquals(8, l.owned(TAR));
		assertEquals(0, l.spent(TAR));
	}

	@Test
	public void spendingKeepsAcquiredButReducesOwned()
	{
		ItemLedger l = new ItemLedger();
		l.observe(INV, counts());
		l.commit();
		l.observe(INV, counts(TAR, 5));
		l.commit();
		l.observe(INV, counts(TAR, 0));
		l.commit();
		assertEquals(5, l.acquired(TAR));  // sticky
		assertEquals(0, l.owned(TAR));
		assertEquals(5, l.spent(TAR));
	}

	@Test
	public void transferBetweenOwnContainersDoesNotInflateAcquired()
	{
		// Regression: withdrawing from the bank must NOT read as an acquisition.
		ItemLedger l = new ItemLedger();
		l.observe(BANK, counts(TAR, 5)); // seed bank holding 5
		l.observe(INV, counts());        // seed empty inventory
		l.commit();
		assertEquals(0, l.acquired(TAR));
		assertEquals(5, l.owned(TAR));

		// One tick: bank 5 -> 0, inventory 0 -> 5 (a withdrawal). Net zero.
		l.observe(INV, counts(TAR, 5));
		l.observe(BANK, counts());
		l.commit();
		assertEquals("withdrawal must not inflate acquired", 0, l.acquired(TAR));
		assertEquals(5, l.owned(TAR));
		assertEquals(0, l.spent(TAR));
	}

	@Test
	public void distinguishesBankedFromUsedOrDropped()
	{
		ItemLedger l = new ItemLedger();
		l.observe(INV, counts());
		l.observe(BANK, counts());
		l.commit();
		l.observe(INV, counts(TAR, 5)); // acquire 5 in inventory
		l.commit();
		// one tick: move 3 to the bank
		l.observe(INV, counts(TAR, 2));
		l.observe(BANK, counts(TAR, 3));
		l.commit();
		// one tick: drop the remaining 2
		l.observe(INV, counts());
		l.commit();

		assertEquals(5, l.acquired(TAR));       // total obtained
		assertEquals(0, l.ownedIn(INV, TAR));   // none carried
		assertEquals(3, l.ownedIn(BANK, TAR));  // moved to bank
		assertEquals(2, l.spent(TAR));          // used/dropped
	}

	@Test
	public void genuineGainsAcrossContainersAccrue()
	{
		ItemLedger l = new ItemLedger();
		l.observe(INV, counts());
		l.observe(BANK, counts());
		l.commit();
		l.observe(INV, counts(TAR, 2));
		l.observe(BANK, counts(TAR, 5));
		l.commit();
		assertEquals(7, l.acquired(TAR));
		assertEquals(7, l.owned(TAR));
	}

	@Test
	public void acquiredStringRoundTrip()
	{
		// Mirrors how the plugin now saves/loads the ledger: a plain "id:count;..." string (no Gson).
		ItemLedger l = new ItemLedger();
		l.observe(INV, counts());
		l.commit();
		l.observe(INV, counts(TAR, 5, COINS, 100));
		l.commit();

		String saved = l.acquiredToString();
		ItemLedger restored = new ItemLedger();
		restored.acquiredFromString(saved);
		assertEquals(5, restored.acquired(TAR));
		assertEquals(100, restored.acquired(COINS));
	}

	@Test
	public void acquiredFromStringIgnoresMalformedAndEmpty()
	{
		ItemLedger l = new ItemLedger();
		l.acquiredFromString(null);
		assertEquals(0, l.acquired(TAR));
		l.acquiredFromString("1939:5;garbage;:7;995:100");
		assertEquals(5, l.acquired(1939));
		assertEquals(100, l.acquired(995));
	}

	@Test
	public void itemsOfInterestFilterIgnoresOthers()
	{
		ItemLedger l = new ItemLedger();
		l.setItemsOfInterest(Collections.singleton(TAR));
		l.observe(INV, counts());
		l.commit();
		l.observe(INV, counts(TAR, 5, COINS, 1000));
		l.commit();
		assertEquals(5, l.acquired(TAR));
		assertEquals(0, l.acquired(COINS)); // not of interest
	}

	@Test
	public void reloginRestoresAcquiredWithoutDoubleCounting()
	{
		ItemLedger l = new ItemLedger();
		l.observe(INV, counts());
		l.commit();
		l.observe(INV, counts(TAR, 5)); // acquire 5
		l.commit();
		String saved = l.acquiredToString();

		// New session = what loadLedger does: restore acquired string, then re-seed.
		ItemLedger relogged = new ItemLedger();
		relogged.acquiredFromString(saved);
		relogged.clearSnapshots();
		assertEquals(5, relogged.acquired(TAR)); // history restored across sessions

		// First observe after login seeds the held items — must NOT re-count them as acquired.
		relogged.observe(INV, counts(TAR, 5));
		relogged.commit();
		assertEquals(5, relogged.acquired(TAR));
	}
}
