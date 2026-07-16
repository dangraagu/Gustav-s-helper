/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide;

import com.google.gson.Gson;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.osirisguide.engine.ConditionContext;
import com.osirisguide.engine.DialogueDb;
import com.osirisguide.engine.Progression;
import com.osirisguide.engine.Route;
import com.osirisguide.engine.RouteLoader;
import com.osirisguide.engine.RouteStep;
import com.osirisguide.engine.ledger.ItemLedger;
import com.osirisguide.overlay.DialogueOverlay;
import com.osirisguide.overlay.OsirisItemOverlay;
import com.osirisguide.overlay.OsirisMinimapOverlay;
import com.osirisguide.overlay.OsirisWorldOverlay;
import com.osirisguide.overlay.WorldMapMarker;
import com.osirisguide.panel.OsirisGuidePanel;
import com.osirisguide.panel.PanelActions;
import com.osirisguide.panel.PanelPresenter;
import java.awt.image.BufferedImage;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import javax.inject.Inject;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Client;
import net.runelite.api.GameObject;
import net.runelite.api.GameState;
import net.runelite.api.InventoryID;
import net.runelite.api.Item;
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
import net.runelite.client.ui.overlay.worldmap.WorldMapPointManager;
import net.runelite.client.util.ImageUtil;

@Slf4j
@PluginDescriptor(
	name = "Gustav's Helper",
	description = "Step-by-step ironman progression helper following the ironman.guide route",
	tags = {"ironman", "quest", "guide", "progression", "osiris", "efficiency"}
)
public class OsirisGuidePlugin extends Plugin
{
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
	private DialogueOverlay dialogueOverlay;
	@Inject
	private ItemManager itemManager;
	@Inject
	private WorldMapPointManager worldMapPointManager;

	// Loaded guide state (rebuilt by loadGuide()).
	private Route route;
	private Progression progression;
	private ItemLedger ledger;

	// UI + collaborators (built in startUp()).
	private OsirisGuidePanel panel;
	private PanelPresenter presenter;
	private NavigationButton navButton;
	private BufferedImage pluginIcon;
	private WorldMapMarker worldMapMarker;
	private GuideStorage storage;

	// Transient bookkeeping.
	private boolean pendingReconcile;
	private boolean ledgerDirty;
	private boolean ledgerViewDirty;
	private String loadedGuideId;
	private String accountKey;
	private String lastCurrentStepId;
	private int wantedObjectId = -1;
	private int wantedNpcId = -1;
	private int tickCounter;

	@Provides
	OsirisGuideConfig provideConfig(ConfigManager configManager)
	{
		return configManager.getConfig(OsirisGuideConfig.class);
	}

	@Provides
	@Singleton
	DialogueDb provideDialogueDb(Gson gson)
	{
		return DialogueDb.load(gson);
	}

	@Override
	protected void startUp()
	{
		storage = new GuideStorage(configManager);
		worldMapMarker = new WorldMapMarker(worldMapPointManager);
		loadGuide();

		panel = new OsirisGuidePanel(new Actions());
		presenter = new PanelPresenter(panel, itemManager);
		pluginIcon = ImageUtil.loadImageResource(getClass(), "/com/osirisguide/icon.png");
		navButton = NavigationButton.builder()
			.tooltip("Gustav's Helper")
			.icon(pluginIcon)
			.priority(7)
			.panel(panel)
			.build();
		clientToolbar.addNavigation(navButton);

		overlayManager.add(worldOverlay);
		overlayManager.add(minimapOverlay);
		overlayManager.add(itemOverlay);
		overlayManager.add(dialogueOverlay);

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
		log.debug("Gustav's Helper started: {} steps", route.size());
	}

	@Override
	protected void shutDown()
	{
		persist();
		persistLedger();
		overlayManager.remove(worldOverlay);
		overlayManager.remove(minimapOverlay);
		overlayManager.remove(itemOverlay);
		overlayManager.remove(dialogueOverlay);
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

	/** The guide actually loaded in memory. Persistence keys off THIS, not config.guide(), because
	 *  onConfigChanged fires after the config already changed — so a flush of the outgoing guide must
	 *  still use the outgoing guide's id. */
	private String guideId()
	{
		return loadedGuideId;
	}

	/** (Re)loads the selected guide's route + a fresh progression/ledger, and this account's saved
	 *  per-guide progress/ledger. Called at start-up and whenever the guide picker changes. */
	private void loadGuide()
	{
		loadedGuideId = config.guide().getId();
		route = RouteLoader.load(gson, loadedGuideId);
		progression = new Progression(route, config.mode());
		ledger = new ItemLedger();
		ledger.setItemsOfInterest(route.referencedItemIds());
		if (presenter != null) // built after the first loadGuide(); a fresh presenter already starts clean
		{
			presenter.invalidate();
		}
		lastCurrentStepId = null;
		if (accountKey != null)
		{
			loadPersisted(accountKey);
			loadLedger(accountKey);
		}
		pendingReconcile = true;
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
			// Milestone-fold: once a later step is done, auto-complete the manual flavour steps behind
			// it so the route advances by itself instead of stalling on an untriggerable "sell/drop" step.
			if (config.autoAdvance() && progression.foldManualBehindMilestones())
			{
				changed = true;
			}
		}
		catch (RuntimeException ex)
		{
			// Never let a bad evaluation wedge the tick loop or leave pendingReconcile stuck true.
			log.warn("Gustav's Helper: tick evaluation failed", ex);
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
		if ("guide".equals(e.getKey()))
		{
			clientThread.invoke(() ->
			{
				persist();          // flush the old guide's progress/ledger before switching
				persistLedger();
				loadGuide();        // route + progression + ledger + saved state for the new guide
				recompute(true);
			});
		}
		else if ("mode".equals(e.getKey()))
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
				NPC npc = findNpc(wantedNpcId);
				if (npc != null)
				{
					state.setTargetNpc(npc);
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
			log.debug("Gustav's Helper: target scan failed", ex);
		}
	}

	/** First loaded NPC with the given id, or null if none is in the scene. */
	private NPC findNpc(int id)
	{
		for (NPC npc : client.getNpcs())
		{
			if (npc != null && npc.getId() == id)
			{
				return npc;
			}
		}
		return null;
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
		presenter.showProgress(progression, route, ctx);
	}

	private void updateWorldMapPoint(RouteStep step)
	{
		WorldPoint target = step == null ? null : step.getWorldPoint();
		String tooltip = step == null ? null : step.getTitle();
		worldMapMarker.show(target, pluginIcon, tooltip);
	}

	private void clearWorldMapPoint()
	{
		if (worldMapMarker != null)
		{
			worldMapMarker.clear();
		}
	}

	// ---- Ledger view --------------------------------------------------------

	private void refreshLedger()
	{
		presenter.showLedger(ledger, client.getGameState() == GameState.LOGGED_IN);
	}

	// ---- Persistence --------------------------------------------------------

	private void persist()
	{
		if (progression == null || accountKey == null)
		{
			return;
		}
		storage.saveProgress(guideId(), accountKey, progression);
	}

	private void loadPersisted(String key)
	{
		storage.loadProgress(guideId(), key, progression);
	}

	private void persistLedger()
	{
		if (ledger == null || accountKey == null)
		{
			return;
		}
		storage.saveLedger(guideId(), accountKey, ledger);
	}

	private void loadLedger(String key)
	{
		if (ledger == null)
		{
			return;
		}
		// loadLedger also re-seeds live tracking so owned/spent rebuild from this login's containers.
		storage.loadLedger(guideId(), key, ledger);
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
