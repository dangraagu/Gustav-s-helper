/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.panel;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.GridLayout;
import javax.swing.BorderFactory;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JProgressBar;
import javax.swing.JTabbedPane;
import javax.swing.SwingUtilities;
import net.runelite.client.ui.ColorScheme;
import net.runelite.client.ui.FontManager;
import net.runelite.client.ui.PluginPanel;
import net.runelite.client.util.LinkBrowser;

/**
 * Two-tab side panel: <b>Guide</b> (overall progress, current step with requirements and manual
 * Done/Skip, lookahead) and <b>Ledger</b> (per-item acquired / owned / spent, with totals).
 */
public class OsirisGuidePanel extends PluginPanel
{
	private final PanelActions actions;

	// Guide tab
	private final JLabel progressLabel = new JLabel();
	private final JProgressBar progressBar = new JProgressBar(0, 100);
	private final JLabel sectionLabel = new JLabel();
	private final JLabel titleLabel = new JLabel();
	private final JLabel textLabel = new JLabel();
	private final JPanel reqContainer = new JPanel();
	private final JPanel upcomingContainer = new JPanel();
	private final JLabel upcomingHeader = new JLabel("Coming up");
	private final JButton doneButton = new JButton("Done");
	private final JButton skipButton = new JButton("Skip");
	private final JButton wikiButton = new JButton("Wiki");
	private final JButton resetButton = new JButton("Reset progress");
	private String wikiUrl;

	// Ledger tab
	private final JLabel ledgerTotals = new JLabel();
	private final JLabel ledgerEmpty = new JLabel();
	private final JPanel ledgerRows = new JPanel();

	public OsirisGuidePanel(PanelActions actions)
	{
		this.actions = actions;
		setLayout(new BorderLayout());
		setBorder(BorderFactory.createEmptyBorder(6, 6, 6, 6));

		JTabbedPane tabs = new JTabbedPane();
		tabs.addTab("Guide", buildGuideTab());
		tabs.addTab("Ledger", buildLedgerTab());
		add(tabs, BorderLayout.CENTER);

		wireActions();
	}

	// ---- Guide tab ----------------------------------------------------------

	private JPanel buildGuideTab()
	{
		JPanel tab = new JPanel(new BorderLayout());
		tab.setBorder(BorderFactory.createEmptyBorder(6, 2, 2, 2));
		tab.add(buildGuideNorth(), BorderLayout.NORTH);
		tab.add(buildGuideCenter(), BorderLayout.CENTER);
		tab.add(buildGuideSouth(), BorderLayout.SOUTH);
		return tab;
	}

	private JPanel buildGuideNorth()
	{
		JPanel north = new JPanel();
		north.setLayout(new BoxLayout(north, BoxLayout.Y_AXIS));

		JLabel header = new JLabel("Osiris Guide");
		header.setFont(FontManager.getRunescapeBoldFont());
		header.setAlignmentX(Component.LEFT_ALIGNMENT);

		progressLabel.setForeground(Color.LIGHT_GRAY);
		progressLabel.setAlignmentX(Component.LEFT_ALIGNMENT);

		progressBar.setStringPainted(true);
		progressBar.setAlignmentX(Component.LEFT_ALIGNMENT);
		progressBar.setMaximumSize(new Dimension(Integer.MAX_VALUE, 18));

		north.add(header);
		north.add(progressLabel);
		north.add(progressBar);
		return north;
	}

	private JPanel buildGuideCenter()
	{
		JPanel center = new JPanel();
		center.setLayout(new BoxLayout(center, BoxLayout.Y_AXIS));
		center.setBorder(BorderFactory.createEmptyBorder(10, 0, 0, 0));

		sectionLabel.setForeground(ColorScheme.BRAND_ORANGE);
		sectionLabel.setAlignmentX(Component.LEFT_ALIGNMENT);

		titleLabel.setFont(FontManager.getRunescapeBoldFont());
		titleLabel.setAlignmentX(Component.LEFT_ALIGNMENT);

		textLabel.setAlignmentX(Component.LEFT_ALIGNMENT);
		textLabel.setForeground(Color.LIGHT_GRAY);

		reqContainer.setLayout(new BoxLayout(reqContainer, BoxLayout.Y_AXIS));
		reqContainer.setAlignmentX(Component.LEFT_ALIGNMENT);
		reqContainer.setBorder(BorderFactory.createEmptyBorder(6, 0, 6, 0));

		JPanel buttons = new JPanel(new GridLayout(1, 3, 4, 0));
		buttons.setAlignmentX(Component.LEFT_ALIGNMENT);
		buttons.setMaximumSize(new Dimension(Integer.MAX_VALUE, 26));
		buttons.add(doneButton);
		buttons.add(skipButton);
		buttons.add(wikiButton);

		upcomingHeader.setFont(FontManager.getRunescapeSmallFont());
		upcomingHeader.setForeground(Color.GRAY);
		upcomingHeader.setAlignmentX(Component.LEFT_ALIGNMENT);
		upcomingHeader.setBorder(BorderFactory.createEmptyBorder(12, 0, 4, 0));

		upcomingContainer.setLayout(new BoxLayout(upcomingContainer, BoxLayout.Y_AXIS));
		upcomingContainer.setAlignmentX(Component.LEFT_ALIGNMENT);

		center.add(sectionLabel);
		center.add(titleLabel);
		center.add(textLabel);
		center.add(reqContainer);
		center.add(buttons);
		center.add(upcomingHeader);
		center.add(upcomingContainer);
		return center;
	}

	private JPanel buildGuideSouth()
	{
		JPanel south = new JPanel(new BorderLayout());
		south.setBorder(BorderFactory.createEmptyBorder(12, 0, 0, 0));
		south.add(resetButton, BorderLayout.CENTER);
		return south;
	}

	// ---- Ledger tab ---------------------------------------------------------

	private JPanel buildLedgerTab()
	{
		JPanel tab = new JPanel(new BorderLayout());
		tab.setBorder(BorderFactory.createEmptyBorder(8, 2, 2, 2));

		JLabel header = new JLabel("Item ledger");
		header.setFont(FontManager.getRunescapeBoldFont());

		ledgerTotals.setForeground(Color.LIGHT_GRAY);
		ledgerTotals.setBorder(BorderFactory.createEmptyBorder(2, 0, 8, 0));

		ledgerEmpty.setForeground(Color.GRAY);
		ledgerEmpty.setText("<html><body style='width:190px'>Items the guide references appear here as you"
			+ " obtain and spend them. Nothing is tracked yet.</body></html>");

		JPanel top = new JPanel();
		top.setLayout(new BoxLayout(top, BoxLayout.Y_AXIS));
		header.setAlignmentX(Component.LEFT_ALIGNMENT);
		ledgerTotals.setAlignmentX(Component.LEFT_ALIGNMENT);
		ledgerEmpty.setAlignmentX(Component.LEFT_ALIGNMENT);
		top.add(header);
		top.add(ledgerTotals);
		top.add(ledgerEmpty);

		ledgerRows.setLayout(new BoxLayout(ledgerRows, BoxLayout.Y_AXIS));

		tab.add(top, BorderLayout.NORTH);
		tab.add(ledgerRows, BorderLayout.CENTER);
		return tab;
	}

	private void wireActions()
	{
		doneButton.addActionListener(e -> actions.completeCurrent());
		skipButton.addActionListener(e -> actions.skipCurrent());
		resetButton.addActionListener(e -> actions.resetProgress());
		wikiButton.addActionListener(e ->
		{
			if (wikiUrl != null && !wikiUrl.isEmpty())
			{
				LinkBrowser.browse(wikiUrl);
			}
		});
	}

	// ---- Updates (thread-safe) ---------------------------------------------

	/** Renders the guide-tab snapshot on the Swing thread. */
	public void update(PanelModel m)
	{
		if (!SwingUtilities.isEventDispatchThread())
		{
			SwingUtilities.invokeLater(() -> update(m));
			return;
		}

		progressBar.setValue(m.percent);
		progressBar.setString(m.percent + "%");

		if (m.routeEmpty)
		{
			progressLabel.setText("No route loaded");
		}
		else if (!m.loggedIn)
		{
			progressLabel.setText("Log in to track progress");
		}
		else
		{
			progressLabel.setText(m.mode + " — " + m.completed + " / " + m.total + " steps");
		}

		reqContainer.removeAll();
		upcomingContainer.removeAll();
		this.wikiUrl = m.wikiUrl;

		boolean hasCurrent = m.loggedIn && !m.finished && !m.routeEmpty;

		if (m.finished && !m.routeEmpty && m.loggedIn)
		{
			sectionLabel.setText("");
			titleLabel.setText("Route complete ✓");
			textLabel.setText("<html><body style='width:190px'>You have finished the guide. Nice.</body></html>");
		}
		else if (hasCurrent)
		{
			sectionLabel.setText(m.section);
			titleLabel.setText(m.title);
			textLabel.setText("<html><body style='width:190px'>" + escape(m.text) + "</body></html>");
			for (PanelModel.ReqView r : m.requirements)
			{
				JLabel l = new JLabel((r.met ? "✓ " : "✗ ") + r.text);
				l.setForeground(r.met ? ColorScheme.PROGRESS_COMPLETE_COLOR : ColorScheme.PROGRESS_ERROR_COLOR);
				l.setAlignmentX(Component.LEFT_ALIGNMENT);
				reqContainer.add(l);
			}
			for (String up : m.upcoming)
			{
				JLabel l = new JLabel("• " + up);
				l.setForeground(Color.GRAY);
				l.setFont(FontManager.getRunescapeSmallFont());
				l.setAlignmentX(Component.LEFT_ALIGNMENT);
				upcomingContainer.add(l);
			}
		}
		else
		{
			sectionLabel.setText("");
			titleLabel.setText("");
			textLabel.setText(m.routeEmpty ? "<html>Route data is missing.</html>" : "");
		}

		doneButton.setEnabled(hasCurrent);
		skipButton.setEnabled(hasCurrent);
		wikiButton.setEnabled(hasCurrent && m.wikiUrl != null && !m.wikiUrl.isEmpty());
		upcomingHeader.setVisible(hasCurrent && !m.upcoming.isEmpty());

		revalidate();
		repaint();
	}

	/** Renders the ledger-tab snapshot on the Swing thread. */
	public void updateLedger(LedgerModel m)
	{
		if (!SwingUtilities.isEventDispatchThread())
		{
			SwingUtilities.invokeLater(() -> updateLedger(m));
			return;
		}

		ledgerRows.removeAll();

		if (!m.loggedIn)
		{
			ledgerTotals.setText("Log in to track items.");
			ledgerEmpty.setVisible(false);
		}
		else if (m.empty || m.rows.isEmpty())
		{
			ledgerTotals.setText("");
			ledgerEmpty.setVisible(true);
		}
		else
		{
			ledgerEmpty.setVisible(false);
			ledgerTotals.setText("<html>Acquired " + m.totalAcquired + " &bull; banked " + m.totalBanked
				+ " &bull; used/dropped " + m.totalUsedDropped + "</html>");

			JPanel headerRow = row("Item", "got", "carry", "bank", "used");
			headerRow.setBorder(BorderFactory.createEmptyBorder(0, 0, 3, 0));
			ledgerRows.add(headerRow);

			for (LedgerModel.Row r : m.rows)
			{
				ledgerRows.add(row(r.name, String.valueOf(r.acquired), String.valueOf(r.carrying),
					String.valueOf(r.banked), String.valueOf(r.usedDropped)));
			}
		}

		revalidate();
		repaint();
	}

	private JPanel row(String name, String got, String carry, String bank, String used)
	{
		JPanel p = new JPanel(new BorderLayout(4, 0));
		p.setMaximumSize(new Dimension(Integer.MAX_VALUE, 18));
		JLabel n = new JLabel(name);
		n.setFont(FontManager.getRunescapeSmallFont());
		JPanel nums = new JPanel(new GridLayout(1, 4, 3, 0));
		nums.add(rightLabel(got));
		nums.add(rightLabel(carry));
		nums.add(rightLabel(bank));
		nums.add(rightLabel(used));
		nums.setPreferredSize(new Dimension(104, 16));
		p.add(n, BorderLayout.CENTER);
		p.add(nums, BorderLayout.EAST);
		return p;
	}

	private JLabel rightLabel(String s)
	{
		JLabel l = new JLabel(s);
		l.setFont(FontManager.getRunescapeSmallFont());
		l.setHorizontalAlignment(JLabel.RIGHT);
		return l;
	}

	private static String escape(String s)
	{
		if (s == null)
		{
			return "";
		}
		return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
	}
}
