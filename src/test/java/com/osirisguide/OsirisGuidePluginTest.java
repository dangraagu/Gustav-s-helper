/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide;

import com.questhelper.QuestHelperPlugin;
import net.runelite.client.RuneLite;
import net.runelite.client.externalplugins.ExternalPluginManager;

/**
 * Dev launcher (fork/questhelper branch): starts RuneLite with BOTH Gustav's Helper and the vendored
 * Quest Helper loaded, so quest steps can drive Quest Helper's own walkthrough. Run {@code ./gradlew run}.
 */
public class OsirisGuidePluginTest
{
	@SuppressWarnings("unchecked")
	public static void main(String[] args) throws Exception
	{
		ExternalPluginManager.loadBuiltin(OsirisGuidePlugin.class, QuestHelperPlugin.class);
		RuneLite.main(args);
	}
}
