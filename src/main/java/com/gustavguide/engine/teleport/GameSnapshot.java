/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine.teleport;

import java.util.Collection;
import net.runelite.api.Skill;

/**
 * Read-only view of the things a teleport requirement checks, so {@link TeleportDb} can decide whether
 * a teleport is UNLOCKED for the player without touching the RuneLite client directly (keeps the picker
 * unit-testable). The plugin supplies a live implementation on the client thread.
 */
public interface GameSnapshot
{
	int skillLevel(Skill skill);

	int totalLevel();

	int combatLevel();

	int questPoints();

	int varbit(int id);

	int varp(int id);

	/** True if the quest with this RuneLite Quest constant name is FINISHED. Unknown name -> false. */
	boolean questFinished(String questConstName);

	/** True if the player owns at least one of these item ids anywhere (inv/bank/equip). */
	boolean ownsAnyItem(Collection<Integer> itemIds);
}
