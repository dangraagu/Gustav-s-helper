/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

/**
 * Where an item condition looks for items.
 */
public enum ItemScope
{
	INVENTORY,
	BANK,
	EQUIPMENT,
	/** Inventory + equipment + bank (the "do you own this anywhere we can see" case). */
	ANY;

	public static ItemScope fromString(String s)
	{
		if (s == null)
		{
			return INVENTORY;
		}
		switch (s.trim().toUpperCase())
		{
			case "BANK":
				return BANK;
			case "EQUIPMENT":
			case "EQUIPPED":
			case "WORN":
				return EQUIPMENT;
			case "ANY":
			case "OWNED":
				return ANY;
			case "INVENTORY":
			case "INV":
			default:
				return INVENTORY;
		}
	}
}
