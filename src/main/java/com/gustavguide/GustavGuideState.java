/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide;

import com.gustavguide.engine.RouteStep;
import javax.inject.Singleton;
import net.runelite.api.NPC;
import net.runelite.api.TileObject;

/**
 * Small shared holder the plugin writes and the overlays read. Kept separate to avoid a
 * Guice injection cycle between the plugin and its overlays. All access happens on the
 * client thread (tick updates and overlay rendering).
 */
@Singleton
public class GustavGuideState
{
	private volatile RouteStep currentStep;
	private volatile TileObject targetObject;
	private volatile NPC targetNpc;

	public RouteStep getCurrentStep()
	{
		return currentStep;
	}

	public void setCurrentStep(RouteStep currentStep)
	{
		this.currentStep = currentStep;
	}

	public TileObject getTargetObject()
	{
		return targetObject;
	}

	public void setTargetObject(TileObject targetObject)
	{
		this.targetObject = targetObject;
	}

	public NPC getTargetNpc()
	{
		return targetNpc;
	}

	public void setTargetNpc(NPC targetNpc)
	{
		this.targetNpc = targetNpc;
	}

	public void clearTargets()
	{
		this.targetObject = null;
		this.targetNpc = null;
	}
}
