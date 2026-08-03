/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide;

import com.google.gson.Gson;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.gustavguide.engine.ConditionContext;
import com.gustavguide.engine.DialogueDb;
import com.gustavguide.engine.Progression;
import com.gustavguide.engine.ReminderTimer;
import com.gustavguide.engine.Route;
import com.gustavguide.engine.RouteLoader;
import com.gustavguide.engine.RouteStep;
import com.gustavguide.engine.ledger.ItemLedger;
import com.gustavguide.engine.teleport.ClientGameSnapshot;
import com.gustavguide.engine.teleport.TeleportDb;
import com.gustavguide.overlay.DialogueOverlay;
import com.gustavguide.overlay.GustavItemOverlay;
import com.gustavguide.overlay.GustavMinimapOverlay;
import com.gustavguide.overlay.GustavWorldOverlay;
import com.gustavguide.overlay.WorldMapMarker;
import com.gustavguide.panel.GustavGuidePanel;
import com.gustavguide.panel.PanelActions;
import com.gustavguide.panel.PanelPresenter;
import java.awt.image.BufferedImage;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
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
import net.runelite.client.Notifier;
import net.runelite.client.callback.ClientThread;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.eventbus.EventBus;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.events.PluginMessage;
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
	description = "Step-by-step ironman progression helper (ironman.guide + OSRS Wiki routes). Suggest more guides via the GitHub repo.",
	tags = {"ironman", "quest", "guide", "progression", "osiris", "efficiency"}
)
public class GustavGuidePlugin extends Plugin
{
	/**
	 * Where the panel's "Report wrong / missing info" button sends step reports.
	 *
	 * <p>This is a forwarding endpoint we control, NOT the Discord webhook. The plugin ships in a public
	 * repo, so anything here is public — a raw webhook URL could be extracted and used to @everyone-ping
	 * the server or delete the webhook outright (and GitHub's secret scanning would likely revoke it
	 * anyway). The forwarder holds the webhook privately, rebuilds the payload so nothing but plain text
	 * gets through, and can rate-limit or block abuse without shipping a new plugin release.
	 * See tools/report-proxy/. Users may override this with their own webhook in the config.</p>
	 */
	private static final String DEFAULT_REPORT_ENDPOINT = "https://gustav.yamaduo.no/report";

	private static final int PANEL_REFRESH_TICKS = 5;
	private static final int NAV_PRIORITY = 7;

	// Birdhouse-run reminder: Verdant Valley, Fossil Island (wiki {{Map}} centre). Visiting anywhere
	// within the radius (re)arms a ~50-minute cycle; when it elapses, a notification fires once.
	private static final WorldPoint BIRDHOUSE_AREA = new WorldPoint(3760, 3760, 0);
	private static final int BIRDHOUSE_RADIUS = 40;
	private static final long BIRDHOUSE_INTERVAL_MS = 50L * 60L * 1000L;

	@Inject
	private Client client;
	@Inject
	private ClientThread clientThread;

	@Inject
	private com.gustavguide.panel.ReportSender reportSender;
	@Inject
	private GustavGuideConfig config;
	@Inject
	private ConfigManager configManager;
	@Inject
	private OverlayManager overlayManager;
	@Inject
	private ClientToolbar clientToolbar;
	@Inject
	private Gson gson;
	@Inject
	private GustavGuideState state;
	@Inject
	private GustavWorldOverlay worldOverlay;
	@Inject
	private GustavMinimapOverlay minimapOverlay;
	@Inject
	private GustavItemOverlay itemOverlay;
	@Inject
	private DialogueOverlay dialogueOverlay;
	@Inject
	private ItemManager itemManager;
	@Inject
	private WorldMapPointManager worldMapPointManager;
	@Inject
	private Notifier notifier;
	@Inject
	private EventBus eventBus;
	@Inject
	private TeleportDb teleportDb;

	// Loaded guide state (rebuilt by loadGuide()).
	private Route route;
	private Progression progression;
	private ItemLedger ledger;

	// UI + collaborators (built in startUp()).
	private GustavGuidePanel panel;
	private PanelPresenter presenter;
	private NavigationButton navButton;
	private BufferedImage pluginIcon;
	private WorldMapMarker worldMapMarker;
	private GuideStorage storage;

	// Birdhouse reminder (per account; loaded on account resolve, persisted periodically).
	private ReminderTimer birdhouseTimer;
	private long birdhousePersistedVisit;

	// Teleport hint / Shortest Path drive.
	private String teleportHint;
	private boolean drivingShortestPath;

	// Transient bookkeeping.
	private boolean pendingReconcile;
	private boolean ledgerDirty;
	private boolean ledgerViewDirty;
	private String loadedGuideId;
	private String accountKey;
	private String lastCurrentStepId;
	private int wantedObjectId = -1;
	private List<Integer> wantedNpcIds = Collections.emptyList();
	private int tickCounter;

	/** Version string for a step report — from the jar manifest, "dev" when running from source. */
	private String pluginVersion()
	{
		String v = getClass().getPackage() == null ? null : getClass().getPackage().getImplementationVersion();
		return v == null ? "dev" : v;
	}

	@Provides
	GustavGuideConfig provideConfig(ConfigManager configManager)
	{
		return configManager.getConfig(GustavGuideConfig.class);
	}

	@Provides
	@Singleton
	DialogueDb provideDialogueDb(Gson gson)
	{
		return DialogueDb.load(gson);
	}

	@Provides
	@Singleton
	TeleportDb provideTeleportDb(Gson gson)
	{
		return TeleportDb.load(gson);
	}

	@Override
	protected void startUp()
	{
		storage = new GuideStorage(configManager);
		worldMapMarker = new WorldMapMarker(worldMapPointManager);
		loadGuide();

		panel = new GustavGuidePanel(new Actions());
		presenter = new PanelPresenter(panel, itemManager);
		// loadGuide() ran before the presenter existed, so seed it here or the report preview would show
		// an empty guide until the user switches guide.
		presenter.setGuide(config.guide().getId(), config.guide().toString());
		presenter.setPluginVersion(pluginVersion());
		pluginIcon = ImageUtil.loadImageResource(getClass(), "/com/gustavguide/icon.png");
		navButton = NavigationButton.builder()
			.tooltip("Gustav's Helper")
			.icon(pluginIcon)
			.priority(NAV_PRIORITY)
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
		persistBirdhouse();
		birdhouseTimer = null;
		overlayManager.remove(worldOverlay);
		overlayManager.remove(minimapOverlay);
		overlayManager.remove(itemOverlay);
		overlayManager.remove(dialogueOverlay);
		clearWorldMapPoint();
		driveShortestPath(null); // stop pathing the Shortest Path plugin when we shut down
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
		if (presenter != null)
		{
			presenter.setGuide(config.guide().getId(), config.guide().toString());
			presenter.setPluginVersion(pluginVersion());
		}
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
			persistBirdhouse();
			birdhouseTimer = null; // per-account: never let one account's cycle notify another
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
		boolean changed = evaluateProgression(ctx);

		handleBirdhouseReminder(ctx);

		boolean periodic = runPeriodicPersistence();

		// A container change (pickup / bank / drop / use) refreshes the ledger view promptly, even
		// when 'acquired' didn't rise — so the used/dropped column updates the moment you drop an item.
		boolean refresh = changed || didReconcile || periodic || ledgerViewDirty;
		ledgerViewDirty = false;
		recompute(refresh);
	}

	/** Reconcile / auto-advance / milestone-fold this tick; persists when anything changed and returns it. */
	private boolean evaluateProgression(ConditionContext ctx)
	{
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
		return changed;
	}

	/** Birdhouse-run reminder: being at the birdhouses (re)arms the cycle; away + elapsed -> one notify. */
	private void handleBirdhouseReminder(ConditionContext ctx)
	{
		if (config.birdhouseReminder() && birdhouseTimer != null)
		{
			WorldPoint here = ctx.playerLocation();
			long now = System.currentTimeMillis();
			if (here != null && BIRDHOUSE_AREA.distanceTo(here) <= BIRDHOUSE_RADIUS)
			{
				birdhouseTimer.visit(now);
			}
			else if (birdhouseTimer.due(now))
			{
				notifier.notify("Gustav's Helper: birdhouse run is ready (Fossil Island)");
			}
		}
	}

	/** Periodic (every PANEL_REFRESH_TICKS) ledger + birdhouse flush; returns whether this was a periodic tick. */
	private boolean runPeriodicPersistence()
	{
		tickCounter++;
		boolean periodic = (tickCounter % PANEL_REFRESH_TICKS == 0);
		if (ledgerDirty && periodic)
		{
			persistLedger();
			ledgerDirty = false;
		}
		if (periodic)
		{
			persistBirdhouse();
		}
		return periodic;
	}

	@Subscribe
	public void onConfigChanged(ConfigChanged e)
	{
		if (!GustavGuideConfig.GROUP.equals(e.getGroup()) || progression == null)
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
		else if ("driveShortestPath".equals(e.getKey()) || "teleportHint".equals(e.getKey()))
		{
			// Apply the toggle immediately instead of waiting for the next step change: re-drive or
			// CLEAR Shortest Path, and refresh the panel so the hint appears/disappears now.
			clientThread.invoke(() ->
			{
				RouteStep current = progression.getCurrentStep();
				applyShortestPathDrive(current);
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
		if (npc != null && wantedNpcIds.contains(npc.getId()))
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
		birdhousePersistedVisit = storage.loadBirdhouseVisit(key);
		birdhouseTimer = new ReminderTimer(BIRDHOUSE_INTERVAL_MS, birdhousePersistedVisit);
		pendingReconcile = true;
		return true;
	}

	/** Persist the birdhouse cycle when it changed (cheap no-op otherwise). */
	private void persistBirdhouse()
	{
		if (birdhouseTimer != null && accountKey != null
			&& birdhouseTimer.getLastVisit() != birdhousePersistedVisit)
		{
			storage.saveBirdhouseVisit(accountKey, birdhouseTimer.getLastVisit());
			birdhousePersistedVisit = birdhouseTimer.getLastVisit();
		}
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
		wantedNpcIds = Collections.emptyList();
		updateWorldMapPoint(current);
		// Drive Shortest Path to this step's destination (on step change only); the panel hint is
		// recomputed separately in refreshPanel so it stays fresh within a step.
		applyShortestPathDrive(current);
		if (current == null)
		{
			return;
		}
		wantedObjectId = current.getHighlightObjectId();
		wantedNpcIds = current.getHighlightNpcIds();
		if (client.getGameState() != GameState.LOGGED_IN)
		{
			return;
		}
		try
		{
			if (!wantedNpcIds.isEmpty())
			{
				NPC npc = findNpc(wantedNpcIds);
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

	/** First loaded NPC whose id is one of the wanted ids ("any man"), or null if none is in scene. */
	private NPC findNpc(List<Integer> ids)
	{
		for (NPC npc : client.getNpcs())
		{
			if (npc != null && ids.contains(npc.getId()))
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
		// Recompute the teleport hint on every panel refresh (cheap) so it self-corrects on a mid-step
		// spellbook/level change; the Shortest Path DRIVE is posted only on step change (below).
		computeTeleportHint(progression == null ? null : progression.getCurrentStep());
		presenter.showProgress(progression, route, ctx, teleportHint);
	}

	// ---- Teleport hint + Shortest Path drive --------------------------------
	// Only for a step with a real destination that is meaningfully far. The hint suggests the fastest
	// UNLOCKED teleport (checked against live game state); the drive posts the destination to the
	// Shortest Path plugin over RuneLite's plugin-message bus (a no-op if it isn't installed).
	private static final int GUIDE_MIN_DIST = 25;

	/** The step's destination if it's a worthwhile far target to guide toward, else null. */
	private WorldPoint guideDest(RouteStep step)
	{
		WorldPoint dest = step == null ? null : step.getWorldPoint();
		if (dest == null || client.getGameState() != GameState.LOGGED_IN)
		{
			return null;
		}
		Player p = client.getLocalPlayer();
		WorldPoint here = p == null ? null : p.getWorldLocation();
		return (here == null || here.distanceTo(dest) > GUIDE_MIN_DIST) ? dest : null;
	}

	/** Recompute the fastest-unlocked-teleport hint string (no bus post). */
	private void computeTeleportHint(RouteStep step)
	{
		teleportHint = null;
		WorldPoint dest = guideDest(step);
		if (dest == null || !config.teleportHint() || teleportDb.isEmpty())
		{
			return;
		}
		Player p = client.getLocalPlayer();
		TeleportDb.Teleport t = teleportDb.best(dest, p == null ? null : p.getWorldLocation(),
			new ClientGameSnapshot(client));
		if (t != null)
		{
			teleportHint = "Fastest: " + t.getName()
				+ (t.getReqText() != null && !t.getReqText().isEmpty() ? " (" + t.getReqText() + ")" : "");
		}
	}

	/** Drive Shortest Path to {@code step}'s guide destination when the toggle is on, else clear it. */
	private void applyShortestPathDrive(RouteStep step)
	{
		driveShortestPath(config.driveShortestPath() ? guideDest(step) : null);
	}

	/** Path the Shortest Path plugin to {@code dest} (or clear it) via the plugin-message bus. */
	private void driveShortestPath(WorldPoint dest)
	{
		if (dest != null)
		{
			Map<String, Object> data = new HashMap<>();
			data.put("target", dest);
			eventBus.post(new PluginMessage("shortestpath", "path", data));
			drivingShortestPath = true;
		}
		else if (drivingShortestPath)
		{
			eventBus.post(new PluginMessage("shortestpath", "clear"));
			drivingShortestPath = false;
		}
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
			// Intentional: a linear guide has no "skip without doing", so skip == complete the current step.
			completeCurrent();
		}

		@Override
		public void undoLast()
		{
			clientThread.invoke(() ->
			{
				if (progression == null)
				{
					return;
				}
				if (progression.stepBack())
				{
					persist();
					lastCurrentStepId = null;   // force the overlays/world marker to re-point at the reopened step
					recompute(true);
				}
			});
		}

		@Override
		public void reportStep(String reportBody)
		{
			// The body was built + shown on the panel; send it verbatim. No client-thread work needed,
			// so nothing can differ between what the user approved and what is sent.
			String configured = config.reportEndpoint();
			String endpoint = (configured == null || configured.trim().isEmpty())
				? DEFAULT_REPORT_ENDPOINT : configured;
			reportSender.send(endpoint, reportBody, panel::showReportResult);
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
