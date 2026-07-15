/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide;

import com.google.gson.Gson;
import com.google.inject.Provides;
import com.osirisguide.engine.ConditionContext;
import com.osirisguide.engine.Progression;
import com.osirisguide.engine.Route;
import com.osirisguide.engine.RouteLoader;
import com.osirisguide.engine.RouteStep;
import com.osirisguide.engine.ledger.ItemLedger;
import com.osirisguide.overlay.OsirisItemOverlay;
import com.osirisguide.overlay.OsirisMinimapOverlay;
import com.osirisguide.overlay.OsirisWorldOverlay;
import com.osirisguide.panel.LedgerModel;
import com.osirisguide.panel.OsirisGuidePanel;
import com.osirisguide.panel.PanelActions;
import com.osirisguide.panel.PanelModel;
import com.osirisguide.requirement.Requirement;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import javax.inject.Inject;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Client;
import net.runelite.api.GameObject;
import net.runelite.api.GameState;
import net.runelite.api.InventoryID;
import net.runelite.api.Item;
import net.runelite.api.ItemComposition;
import net.runelite.api.ItemContainer;
import net.runelite.api.NPC;
import net.runelite.api.Player;
import net.runelite.api.Scene;
import net.runelite.api.Tile;
import net.runelite.api.TileObject;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.GameObjectDespawned;
import net.runelite.api.events.GameObjectSpawned;
import net.runelite.api.events.GameStateChanged;
import net.runelite.api.events.GameTick;
import net.runelite.api.events.ItemContainerChanged;
import net.runelite.api.events.NpcDespawned;
import net.runelite.api.events.NpcSpawned;
import net.runelite.client.callback.ClientThread;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.events.ConfigChanged;
import net.runelite.client.game.ItemManager;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.ui.ClientToolbar;
import net.runelite.client.ui.NavigationButton;
import net.runelite.client.ui.overlay.OverlayManager;
import net.runelite.client.ui.overlay.worldmap.WorldMapPoint;
import net.runelite.client.ui.overlay.worldmap.WorldMapPointManager;
import net.runelite.client.util.ImageUtil;

@Slf4j
@PluginDescriptor(
	name = "Osiris Guide",
	description = "Step-by-step ironman progression helper following the ironman.guide route",
	tags = {"ironman", "quest", "guide", "progression", "osiris", "efficiency"}
)
public class OsirisGuidePlugin extends Plugin
{
	private static final int UPCOMING_COUNT = 5;
	private static final int PANEL_REFRESH_TICKS = 5;

	@Inject
	private Client client;
	@Inject
	private ClientThread clientThread;
	@Inject
	private OsirisGuideConfig config;
	@Inject
	private ConfigManager configManager;
	@Inject
	private OverlayManager overlayManager;
	@Inject
	private ClientToolbar clientToolbar;
	@Inject
	private Gson gson;
	@Inject
	private OsirisGuideState state;
	@Inject
	private OsirisWorldOverlay worldOverlay;
	@Inject
	private OsirisMinimapOverlay minimapOverlay;
	@Inject
	private OsirisItemOverlay itemOverlay;
	@Inject
	private ItemManager itemManager;
	@Inject
	private WorldMapPointManager worldMapPointManager;

	private Route route;
	private Progression progression;
	private ItemLedger ledger;
	private OsirisGuidePanel panel;
	private NavigationButton navButton;
	private BufferedImage pluginIcon;
	private WorldMapPoint worldMapPoint;

	private boolean pendingReconcile;
	private boolean ledgerDirty;
	private boolean ledgerViewDirty;
	private String accountKey;
	private String lastLedgerSignature;
	private String lastCurrentStepId;
	private int wantedObjectId = -1;
	private int wantedNpcId = -1;
	private int tickCounter;

	@Provides
	OsirisGuideConfig provideConfig(ConfigManager configManager)
	{
		return configManager.getConfig(OsirisGuideConfig.class);
	}

	@Override
	protected void startUp()
	{
		route = RouteLoader.load(gson);
		progression = new Progression(route, config.mode());
		ledger = new ItemLedger();
		ledger.setItemsOfInterest(route.referencedItemIds());
		lastLedgerSignature = null;

		panel = new OsirisGuidePanel(new Actions());
		pluginIcon = ImageUtil.loadImageResource(getClass(), "/com/osirisguide/icon.png");
		navButton = NavigationButton.builder()
			.tooltip("Osiris Guide")
			.icon(pluginIcon)
			.priority(7)
			.panel(panel)
			.build();
		clientToolbar.addNavigation(navButton);

		overlayManager.add(worldOverlay);
		overlayManager.add(minimapOverlay);
		overlayManager.add(itemOverlay);

		if (client.getGameState() == GameState.LOGGED_IN)
		{
			clientThread.invoke(() ->
			{
				onLogin();
				recompute(true);
			});
		}
		else
		{
			refreshPanel(null);
		}
		log.debug("Osiris Guide started: {} steps", route.size());
	}

	@Override
	protected void shutDown()
	{
		persist();
		persistLedger();
		overlayManager.remove(worldOverlay);
		overlayManager.remove(minimapOverlay);
		overlayManager.remove(itemOverlay);
		clearWorldMapPoint();
		if (navButton != null)
		{
			clientToolbar.removeNavigation(navButton);
		}
		state.setCurrentStep(null);
		state.clearTargets();
		panel = null;
		progression = null;
		route = null;
		ledger = null;
		lastCurrentStepId = null;
		accountKey = null;
	}

	// ---- Events -------------------------------------------------------------

	@Subscribe
	public void onGameStateChanged(GameStateChanged e)
	{
		GameState gs = e.getGameState();
		if (gs == GameState.LOGGED_IN)
		{
			onLogin();
		}
		else if (gs == GameState.LOGIN_SCREEN || gs == GameState.HOPPING || gs == GameState.CONNECTION_LOST)
		{
			// Flush under the CURRENT account key, then clear it so nothing is ever written to a stale
			// account after a switch. The next login re-resolves and reloads.
			persist();
			persistLedger();
			ledgerDirty = false;
			accountKey = null;
		}
		else if (gs == GameState.LOADING)
		{
			// Region/scene swap: drop any tracked object/NPC so a stale reference is never drawn.
			state.clearTargets();
		}
	}

	@Subscribe
	public void onGameTick(GameTick e)
	{
		if (progression == null || route == null || route.isEmpty())
		{
			return;
		}
		if (client.getGameState() != GameState.LOGGED_IN)
		{
			return;
		}

		// Ensure the account is resolved (hash/name may lag the LOGGED_IN transition). Until it is,
		// skip evaluation and persistence so one account's state is never written to another's slot.
		if (!resolveAccount())
		{
			return;
		}

		// Fold this tick's observed container changes into the ledger before evaluating conditions.
		if (ledger != null && ledger.commit())
		{
			ledgerDirty = true;
		}

		boolean didReconcile = pendingReconcile;
		ConditionContext ctx = new ConditionContext(client, ledger);
		boolean changed = false;
		try
		{
			if (pendingReconcile)
			{
				changed = progression.reconcileAll(ctx);
			}
			else if (config.autoAdvance())
			{
				changed = progression.process(ctx);
			}
		}
		catch (RuntimeException ex)
		{
			// Never let a bad evaluation wedge the tick loop or leave pendingReconcile stuck true.
			log.warn("Osiris Guide: tick evaluation failed", ex);
		}
		finally
		{
			pendingReconcile = false;
		}

		if (changed)
		{
			persist();
		}

		tickCounter++;
		boolean periodic = (tickCounter % PANEL_REFRESH_TICKS == 0);
		if (ledgerDirty && periodic)
		{
			persistLedger();
			ledgerDirty = false;
		}
		// A container change (pickup / bank / drop / use) refreshes the ledger view promptly, even
		// when 'acquired' didn't rise — so the used/dropped column updates the moment you drop an item.
		boolean refresh = changed || didReconcile || periodic || ledgerViewDirty;
		ledgerViewDirty = false;
		recompute(refresh);
	}

	@Subscribe
	public void onConfigChanged(ConfigChanged e)
	{
		if (!OsirisGuideConfig.GROUP.equals(e.getGroup()) || progression == null)
		{
			return;
		}
		if ("mode".equals(e.getKey()))
		{
			clientThread.invoke(() ->
			{
				progression.setMode(config.mode());
				lastCurrentStepId = null; // force target + panel refresh
				pendingReconcile = true;
				recompute(true);
			});
		}
	}

	@Subscribe
	public void onGameObjectSpawned(GameObjectSpawned e)
	{
		GameObject go = e.getGameObject();
		if (go != null && wantedObjectId >= 0 && go.getId() == wantedObjectId)
		{
			state.setTargetObject(go);
		}
	}

	@Subscribe
	public void onGameObjectDespawned(GameObjectDespawned e)
	{
		GameObject go = e.getGameObject();
		if (go != null && state.getTargetObject() == go)
		{
			state.setTargetObject(null);
		}
	}

	@Subscribe
	public void onNpcSpawned(NpcSpawned e)
	{
		NPC npc = e.getNpc();
		if (npc != null && wantedNpcId >= 0 && npc.getId() == wantedNpcId)
		{
			state.setTargetNpc(npc);
		}
	}

	@Subscribe
	public void onNpcDespawned(NpcDespawned e)
	{
		NPC npc = e.getNpc();
		if (npc != null && state.getTargetNpc() == npc)
		{
			state.setTargetNpc(null);
		}
	}

	@Subscribe
	public void onItemContainerChanged(ItemContainerChanged e)
	{
		if (ledger == null)
		{
			return;
		}
		int id = e.getContainerId();
		if (id != InventoryID.INVENTORY.getId()
			&& id != InventoryID.BANK.getId()
			&& id != InventoryID.EQUIPMENT.getId())
		{
			return;
		}
		ledger.observe(id, toCounts(e.getItemContainer()));
		ledgerViewDirty = true;
	}

	private static Map<Integer, Integer> toCounts(ItemContainer container)
	{
		Map<Integer, Integer> counts = new HashMap<>();
		if (container == null)
		{
			return counts;
		}
		for (Item item : container.getItems())
		{
			if (item == null)
			{
				continue;
			}
			int id = item.getId();
			int qty = item.getQuantity();
			if (id < 0 || qty <= 0)
			{
				continue;
			}
			counts.merge(id, qty, Integer::sum);
		}
		return counts;
	}

	// ---- Core logic ---------------------------------------------------------

	private void onLogin()
	{
		resolveAccount();
	}

	/**
	 * Loads the current account's saved progress + ledger once its key is resolvable. The account
	 * hash / character name may not be populated at the exact LOGGED_IN transition, so this is retried
	 * from {@link #onGameTick} until it resolves — and until then no evaluation or persistence runs,
	 * so one account's state can never be written into another's slot.
	 *
	 * @return true if an account is resolved (safe to evaluate/persist this tick)
	 */
	private boolean resolveAccount()
	{
		if (accountKey != null)
		{
			return true;
		}
		String key = accountKeyFor();
		if (key == null)
		{
			return false;
		}
		accountKey = key;
		loadPersisted(key);
		loadLedger(key);
		pendingReconcile = true;
		return true;
	}

	/**
	 * Per-account storage key: the account hash (unique per RuneScape account) when available,
	 * otherwise the logged-in character name — so progress and the ledger follow the current account.
	 */
	private String accountKeyFor()
	{
		long hash = client.getAccountHash();
		if (hash != -1L)
		{
			return "acc_" + Long.toUnsignedString(hash);
		}
		Player p = client.getLocalPlayer();
		if (p != null && p.getName() != null && !p.getName().isEmpty())
		{
			return "name_" + p.getName().toLowerCase().replaceAll("[^a-z0-9]", "_");
		}
		return null;
	}

	/** Recomputes the current step + targets and optionally refreshes the panel. Client thread. */
	private void recompute(boolean refresh)
	{
		if (progression == null)
		{
			return;
		}
		RouteStep current = progression.getCurrentStep();
		String curId = current == null ? null : current.getId();
		if (!Objects.equals(curId, lastCurrentStepId))
		{
			updateTargets(current);
			lastCurrentStepId = curId;
			refresh = true;
		}
		state.setCurrentStep(current);
		if (refresh)
		{
			ConditionContext ctx = client.getGameState() == GameState.LOGGED_IN
				? new ConditionContext(client, ledger) : null;
			refreshPanel(ctx);
			refreshLedger();
		}
	}

	private void updateTargets(RouteStep current)
	{
		state.clearTargets();
		wantedObjectId = -1;
		wantedNpcId = -1;
		updateWorldMapPoint(current);
		if (current == null)
		{
			return;
		}
		wantedObjectId = current.getHighlightObjectId();
		wantedNpcId = current.getHighlightNpcId();
		if (client.getGameState() != GameState.LOGGED_IN)
		{
			return;
		}
		try
		{
			if (wantedNpcId >= 0)
			{
				for (NPC npc : client.getNpcs())
				{
					if (npc != null && npc.getId() == wantedNpcId)
					{
						state.setTargetNpc(npc);
						break;
					}
				}
			}
			if (wantedObjectId >= 0)
			{
				TileObject found = findObject(wantedObjectId);
				if (found != null)
				{
					state.setTargetObject(found);
				}
			}
		}
		catch (Exception ex)
		{
			log.debug("Osiris Guide: target scan failed", ex);
		}
	}

	private TileObject findObject(int id)
	{
		Scene scene = client.getScene();
		if (scene == null)
		{
			return null;
		}
		Tile[][][] tiles = scene.getTiles();
		int z = client.getPlane();
		if (tiles == null || z < 0 || z >= tiles.length)
		{
			return null;
		}
		for (Tile[] row : tiles[z])
		{
			if (row == null)
			{
				continue;
			}
			for (Tile t : row)
			{
				if (t == null)
				{
					continue;
				}
				for (GameObject go : t.getGameObjects())
				{
					if (go != null && go.getId() == id)
					{
						return go;
					}
				}
				if (t.getWallObject() != null && t.getWallObject().getId() == id)
				{
					return t.getWallObject();
				}
				if (t.getDecorativeObject() != null && t.getDecorativeObject().getId() == id)
				{
					return t.getDecorativeObject();
				}
				if (t.getGroundObject() != null && t.getGroundObject().getId() == id)
				{
					return t.getGroundObject();
				}
			}
		}
		return null;
	}

	// ---- Panel model --------------------------------------------------------

	private void refreshPanel(ConditionContext ctx)
	{
		if (panel == null || progression == null || route == null)
		{
			return;
		}
		PanelModel m = new PanelModel();
		m.mode = progression.getMode().getDisplayName();
		m.routeEmpty = route.isEmpty();
		m.loggedIn = ctx != null;
		m.completed = progression.completedCount();
		m.total = progression.applicableCount();
		m.percent = progression.progressPercent();

		RouteStep current = progression.getCurrentStep();
		m.finished = current == null && !route.isEmpty();

		if (current != null && ctx != null)
		{
			m.section = current.getSection();
			m.title = current.getTitle();
			m.text = current.getText();
			m.wikiUrl = current.getWikiUrl();
			m.currentIsManual = current.isManual();
			for (Requirement r : current.getRequirements())
			{
				m.requirements.add(new PanelModel.ReqView(r.getText(), r.check(ctx)));
			}
			m.upcoming = upcomingTitles(current, UPCOMING_COUNT);
		}
		panel.update(m);
	}

	private List<String> upcomingTitles(RouteStep current, int count)
	{
		List<String> out = new java.util.ArrayList<>();
		int start = route.indexOf(current.getId());
		if (start < 0)
		{
			return out;
		}
		for (int i = start + 1; i < route.size() && out.size() < count; i++)
		{
			RouteStep s = route.get(i);
			if (s.appliesTo(progression.getMode()) && !progression.isComplete(s))
			{
				out.add(s.getTitle());
			}
		}
		return out;
	}

	private void updateWorldMapPoint(RouteStep step)
	{
		clearWorldMapPoint();
		WorldPoint wp = step == null ? null : step.getWorldPoint();
		if (wp == null || pluginIcon == null)
		{
			return;
		}
		worldMapPoint = new WorldMapPoint(wp, pluginIcon);
		// setName is REQUIRED whenever jumpOnClick is set: WorldMapOverlay asserts a non-null name on
		// hover, and with -ea (RuneLite dev mode) a null name throws an AssertionError that escapes the
		// render loop and freezes the client. This is the fix for the world-map-open freeze.
		worldMapPoint.setName("Osiris Guide");
		worldMapPoint.setTooltip(step.getTitle());
		worldMapPoint.setTarget(wp);
		worldMapPoint.setJumpOnClick(true);
		worldMapPoint.setSnapToEdge(true);
		worldMapPointManager.add(worldMapPoint);
	}

	private void clearWorldMapPoint()
	{
		if (worldMapPoint != null)
		{
			worldMapPointManager.remove(worldMapPoint);
			worldMapPoint = null;
		}
	}

	// ---- Ledger view --------------------------------------------------------

	private void refreshLedger()
	{
		if (panel == null || ledger == null)
		{
			return;
		}
		LedgerModel m = new LedgerModel();
		m.loggedIn = client.getGameState() == GameState.LOGGED_IN;
		int invId = InventoryID.INVENTORY.getId();
		int bankId = InventoryID.BANK.getId();
		int equipId = InventoryID.EQUIPMENT.getId();
		Set<Integer> ids = ledger.ledgerItems();
		List<LedgerModel.Row> rows = new ArrayList<>();
		for (int id : ids)
		{
			int acquired = ledger.acquired(id);
			int carrying = ledger.ownedIn(invId, id) + ledger.ownedIn(equipId, id);
			int banked = ledger.ownedIn(bankId, id);
			int usedDropped = ledger.spent(id);
			if (acquired == 0 && carrying == 0 && banked == 0)
			{
				continue; // referenced but never observed yet — don't clutter the ledger
			}
			rows.add(new LedgerModel.Row(id, itemName(id), acquired, carrying, banked, usedDropped));
			m.totalAcquired += acquired;
			m.totalBanked += banked;
			m.totalUsedDropped += usedDropped;
		}
		rows.sort((a, b) -> Integer.compare(b.acquired, a.acquired));
		m.rows = rows;
		m.empty = rows.isEmpty();

		// Coalesce: only rebuild the Swing rows when the numbers actually changed.
		String sig = ledgerSignature(m);
		if (sig.equals(lastLedgerSignature))
		{
			return;
		}
		lastLedgerSignature = sig;
		panel.updateLedger(m);
	}

	private static String ledgerSignature(LedgerModel m)
	{
		StringBuilder sb = new StringBuilder();
		sb.append(m.loggedIn).append(';').append(m.empty).append(';');
		for (LedgerModel.Row r : m.rows)
		{
			sb.append(r.itemId).append(':').append(r.acquired).append(',').append(r.carrying)
				.append(',').append(r.banked).append(',').append(r.usedDropped).append('|');
		}
		return sb.toString();
	}

	private String itemName(int id)
	{
		try
		{
			ItemComposition comp = itemManager.getItemComposition(id);
			if (comp != null && comp.getName() != null && !comp.getName().isEmpty())
			{
				return comp.getName();
			}
		}
		catch (RuntimeException ex)
		{
			log.debug("Osiris Guide: item name lookup failed for {}", id, ex);
		}
		return "Item " + id;
	}

	// ---- Persistence --------------------------------------------------------

	private void persist()
	{
		if (progression == null || accountKey == null)
		{
			return;
		}
		String value = String.join(",", progression.getCompletedIds());
		configManager.setConfiguration(OsirisGuideConfig.GROUP, "progress_" + accountKey, value);
	}

	private void loadPersisted(String key)
	{
		String value = configManager.getConfiguration(OsirisGuideConfig.GROUP, "progress_" + key);
		if (value == null || value.isEmpty())
		{
			progression.setCompletedIds(Collections.emptyList());
			return;
		}
		progression.setCompletedIds(Arrays.asList(value.split(",")));
	}

	private void persistLedger()
	{
		if (ledger == null || accountKey == null)
		{
			return;
		}
		configManager.setConfiguration(OsirisGuideConfig.GROUP, "ledger_" + accountKey,
			gson.toJson(ledger.exportState()));
	}

	private void loadLedger(String key)
	{
		if (ledger == null)
		{
			return;
		}
		String value = configManager.getConfiguration(OsirisGuideConfig.GROUP, "ledger_" + key);
		if (value == null || value.isEmpty())
		{
			ledger.importState(null);
			return;
		}
		try
		{
			ledger.importState(gson.fromJson(value, ItemLedger.State.class));
		}
		catch (RuntimeException ex)
		{
			log.warn("Osiris Guide: could not parse saved ledger; starting fresh", ex);
			ledger.importState(null);
		}
	}

	// ---- Panel actions (Swing thread -> client thread) ----------------------

	private class Actions implements PanelActions
	{
		@Override
		public void completeCurrent()
		{
			clientThread.invoke(() ->
			{
				if (progression == null)
				{
					return;
				}
				RouteStep c = progression.getCurrentStep();
				if (c != null)
				{
					progression.markComplete(c.getId());
					persist();
					recompute(true);
				}
			});
		}

		@Override
		public void skipCurrent()
		{
			completeCurrent();
		}

		@Override
		public void resetProgress()
		{
			clientThread.invoke(() ->
			{
				if (progression == null)
				{
					return;
				}
				progression.reset();
				persist();
				if (ledger != null)
				{
					ledger.reset();
					persistLedger();
				}
				lastCurrentStepId = null;
				recompute(true);
			});
		}
	}
}
