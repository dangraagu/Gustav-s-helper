/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide;

import net.runelite.client.RuneLite;
import net.runelite.client.externalplugins.ExternalPluginManager;

/**
 * Dev launcher: starts RuneLite with the Osiris Guide plugin loaded. Run with {@code ./gradlew run}.
 */
public class OsirisGuidePluginTest
{
	public static void main(String[] args) throws Exception
	{
		ExternalPluginManager.loadBuiltin(OsirisGuidePlugin.class);
		RuneLite.main(args);
	}
}
