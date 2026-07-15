/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.panel;

import java.util.ArrayList;
import java.util.List;

/**
 * Snapshot of the item ledger the plugin builds on the client thread for the Ledger tab.
 */
public class LedgerModel
{
	public static class Row
	{
		public final int itemId;
		public final String name;
		public final int acquired;    // ever obtained
		public final int carrying;    // in inventory + equipped now
		public final int banked;      // in the bank now
		public final int usedDropped; // acquired - carrying - banked (used/dropped/sold/consumed)

		public Row(int itemId, String name, int acquired, int carrying, int banked, int usedDropped)
		{
			this.itemId = itemId;
			this.name = name;
			this.acquired = acquired;
			this.carrying = carrying;
			this.banked = banked;
			this.usedDropped = usedDropped;
		}
	}

	public boolean loggedIn;
	public boolean empty;          // no items are being tracked at all
	public int totalAcquired;
	public int totalBanked;
	public int totalUsedDropped;
	public List<Row> rows = new ArrayList<>();
}
