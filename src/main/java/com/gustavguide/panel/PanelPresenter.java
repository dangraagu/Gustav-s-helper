/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.panel;

import com.gustavguide.engine.ConditionContext;
import com.gustavguide.engine.Progression;
import com.gustavguide.engine.Route;
import com.gustavguide.engine.RouteStep;
import com.gustavguide.engine.ledger.ItemLedger;
import com.gustavguide.requirement.Requirement;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.InventoryID;
import net.runelite.api.ItemComposition;
import net.runelite.client.game.ItemManager;

/**
 * Builds the side-panel view models from the current progression + ledger and pushes them to the
 * {@link GustavGuidePanel}. Holds no game state of its own beyond a signature used to coalesce
 * redundant ledger repaints — keeping all Swing-model construction out of the plugin class.
 */
@Slf4j
public class PanelPresenter
{
	private static final int UPCOMING_COUNT = 5;

	private final GustavGuidePanel panel;
	private final ItemManager itemManager;

	/** Last rendered ledger signature — skip the Swing rebuild when the numbers are unchanged. */
	private String lastLedgerSignature;
	private String guideId = "";
	private String guideName = "";
	private String pluginVersion = "";

	/** Which guide is loaded — carried into a step report so we know which route to fix. */
	public void setGuide(String guideId, String guideName)
	{
		this.guideId = guideId == null ? "" : guideId;
		this.guideName = guideName == null ? "" : guideName;
	}

	public void setPluginVersion(String version)
	{
		this.pluginVersion = version == null ? "" : version;
	}

	public PanelPresenter(GustavGuidePanel panel, ItemManager itemManager)
	{
		this.panel = panel;
		this.itemManager = itemManager;
	}

	/** Forget the coalescing signature so the next {@link #showLedger} always repaints (e.g. after a
	 *  guide switch, where the incoming guide's first ledger must not be suppressed by the old one's). */
	public void invalidate()
	{
		lastLedgerSignature = null;
	}

	/**
	 * Render the progress/current-step view. {@code ctx} is non-null only when logged in; when null the
	 * panel shows the logged-out placeholder.
	 */
	public void showProgress(Progression progression, Route route, ConditionContext ctx)
	{
		showProgress(progression, route, ctx, null);
	}

	public void showProgress(Progression progression, Route route, ConditionContext ctx, String teleportHint)
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
			m.note = current.getNote();
			m.wikiUrl = current.getWikiUrl();
			for (Requirement r : current.getRequirements())
			{
				m.requirements.add(new PanelModel.ReqView(r.getText(), r.check(ctx)));
			}
			m.upcoming = upcomingTitles(progression, route, current, UPCOMING_COUNT);
			m.teleportHint = teleportHint;
			m.stepNumber = applicableIndexOf(progression, route, current);
			m.reportBody = StepReport.body(guideId, guideName, current, m.stepNumber, m.total,
				"", pluginVersion);
			m.canReport = true;
		}
		panel.update(m);
	}

	/** 1-based position of {@code current} among the steps that apply to the active mode. */
	private static int applicableIndexOf(Progression progression, Route route, RouteStep current)
	{
		int n = 0;
		for (RouteStep s : route.getSteps())
		{
			if (s.appliesTo(progression.getMode()))
			{
				n++;
				if (s.getId().equals(current.getId()))
				{
					return n;
				}
			}
		}
		return 0;
	}

	private List<String> upcomingTitles(Progression progression, Route route, RouteStep current, int count)
	{
		List<String> out = new ArrayList<>();
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

	/** Render the item-ledger view. {@code loggedIn} controls the logged-out placeholder. */
	public void showLedger(ItemLedger ledger, boolean loggedIn)
	{
		if (panel == null || ledger == null)
		{
			return;
		}
		LedgerModel m = new LedgerModel();
		m.loggedIn = loggedIn;
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
			log.debug("Gustav's Helper: item name lookup failed for {}", id, ex);
		}
		return "Item " + id;
	}
}
