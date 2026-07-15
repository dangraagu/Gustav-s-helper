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
		public final int acquired;
		public final int owned;
		public final int spent;

		public Row(int itemId, String name, int acquired, int owned, int spent)
		{
			this.itemId = itemId;
			this.name = name;
			this.acquired = acquired;
			this.owned = owned;
			this.spent = spent;
		}
	}

	public boolean loggedIn;
	public boolean empty;          // no items are being tracked at all
	public int totalAcquired;
	public int totalSpent;
	public List<Row> rows = new ArrayList<>();
}
