/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide;

/**
 * The bundled guides the plugin can follow, selected in config. Each value maps to a folder under
 * {@code resources/com/osirisguide/data/guides/<id>/}. To add a guide: drop its data folder, add an
 * entry in {@code data/guides.json}, and add a value here.
 */
public enum Guide
{
	OSIRIS_IRONMAN("osiris-ironman", "Oziris Ironman Guide"),
	B0ATY_HCIM("b0aty-hcim", "B0aty HCIM Guide V3"),
	OPTIMAL_QUEST_IRONMAN("optimal-quest-ironman", "Optimal Quest Guide (Ironman)"),
	IRONMAN_PVM_RUSH("ironman-pvm-rush", "Ironman PvM Rush"),
	BRUHSAILER("bruhsailer", "BRUHsailer Complete Guide");

	private final String id;
	private final String displayName;

	Guide(String id, String displayName)
	{
		this.id = id;
		this.displayName = displayName;
	}

	public String getId()
	{
		return id;
	}

	@Override
	public String toString()
	{
		return displayName; // shown in the config dropdown
	}
}
