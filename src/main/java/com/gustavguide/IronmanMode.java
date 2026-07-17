/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide;

/**
 * Account type the guide is being followed as. Steps may be restricted to a subset of
 * modes via their {@code modes} field; a step with no modes applies to all.
 */
public enum IronmanMode
{
	REGULAR("Regular"),
	HCIM("Hardcore"),
	UIM("Ultimate"),
	GIM("Group");

	private final String displayName;

	IronmanMode(String displayName)
	{
		this.displayName = displayName;
	}

	public String getDisplayName()
	{
		return displayName;
	}

	@Override
	public String toString()
	{
		return displayName;
	}
}
