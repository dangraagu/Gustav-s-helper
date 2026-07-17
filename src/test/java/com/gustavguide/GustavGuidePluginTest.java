/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide;

import net.runelite.client.RuneLite;
import net.runelite.client.externalplugins.ExternalPluginManager;

/**
 * Dev launcher: starts RuneLite with the Gustav's Helper plugin loaded. Run with {@code ./gradlew run}.
 */
public class GustavGuidePluginTest
{
	public static void main(String[] args) throws Exception
	{
		ExternalPluginManager.loadBuiltin(GustavGuidePlugin.class);
		RuneLite.main(args);
	}
}
