/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.panel;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.GridLayout;
import javax.swing.BorderFactory;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JScrollPane;
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
public class GustavGuidePanel extends PluginPanel
{
	/** Width (px) the wrapping HTML labels are constrained to, so text wraps to the panel. */
	private static final int PANEL_HTML_WIDTH = 210;

	private final PanelActions actions;

	// Guide tab
	private final JLabel progressLabel = new JLabel();
	private final JProgressBar progressBar = new JProgressBar(0, 100);
	private final JLabel sectionLabel = new JLabel();
	private final JLabel titleLabel = new JLabel();
	private final JLabel textLabel = new JLabel();
	private final JLabel noteLabel = new JLabel();
	private final JLabel teleportLabel = new JLabel();
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

	public GustavGuidePanel(PanelActions actions)
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
		// The step description can wrap to many lines; inside a fixed-height tab it was clipped at the
		// bottom. Scroll the centre content vertically (never horizontally) so the full text is reachable.
		JScrollPane centerScroll = new JScrollPane(buildGuideCenter(),
			JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED, JScrollPane.HORIZONTAL_SCROLLBAR_NEVER);
		centerScroll.setBorder(BorderFactory.createEmptyBorder(0, 0, 0, 0));
		centerScroll.getVerticalScrollBar().setUnitIncrement(16);
		tab.add(centerScroll, BorderLayout.CENTER);
		tab.add(buildGuideSouth(), BorderLayout.SOUTH);
		return tab;
	}

	private JPanel buildGuideNorth()
	{
		JPanel north = new JPanel();
		north.setLayout(new BoxLayout(north, BoxLayout.Y_AXIS));

		JLabel header = new JLabel("Gustav's Helper");
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
		// Bigger, more legible current-step description (the main thing the user reads each step).
		textLabel.setFont(FontManager.getRunescapeFont().deriveFont(FontManager.getRunescapeFont().getSize2D() + 2f));

		noteLabel.setAlignmentX(Component.LEFT_ALIGNMENT);
		noteLabel.setForeground(ColorScheme.BRAND_ORANGE);
		noteLabel.setFont(FontManager.getRunescapeSmallFont());
		noteLabel.setBorder(BorderFactory.createEmptyBorder(4, 0, 0, 0));

		teleportLabel.setAlignmentX(Component.LEFT_ALIGNMENT);
		teleportLabel.setForeground(ColorScheme.PROGRESS_INPROGRESS_COLOR);
		teleportLabel.setFont(FontManager.getRunescapeSmallFont());
		teleportLabel.setBorder(BorderFactory.createEmptyBorder(4, 0, 0, 0));

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
		center.add(noteLabel);
		center.add(teleportLabel);
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
		ledgerEmpty.setText(wrap("Items the guide references appear here as you"
			+ " obtain and spend them. Nothing is tracked yet."));

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
		resetButton.addActionListener(e ->
		{
			// Confirm first — a stray click otherwise wipes every completed step + the ledger for this
			// guide on this account (and on a developed account they re-complete from live state anyway).
			int choice = JOptionPane.showConfirmDialog(resetButton,
				"Reset progress for the current guide on this account?\n"
					+ "This clears completed steps and the item ledger for this guide only.",
				"Reset guide progress", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE);
			if (choice == JOptionPane.YES_OPTION)
			{
				actions.resetProgress();
			}
		});
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
			// "… — 259 / 971 done" reads as a COUNT (completed of total), not a step index, so a
			// developed account resuming mid-route isn't misread as "stuck on step 259".
			progressLabel.setText(m.mode + " — " + m.completed + " / " + m.total + " done");
		}

		reqContainer.removeAll();
		upcomingContainer.removeAll();
		this.wikiUrl = m.wikiUrl;

		boolean hasCurrent = m.loggedIn && !m.finished && !m.routeEmpty;

		noteLabel.setVisible(false);
		teleportLabel.setVisible(false);
		if (m.finished && !m.routeEmpty && m.loggedIn)
		{
			sectionLabel.setText("");
			titleLabel.setText("Route complete ✓");
			textLabel.setText(wrap("You have finished the guide. Nice."));
		}
		else if (hasCurrent)
		{
			sectionLabel.setText(m.section);
			titleLabel.setText(m.title);
			textLabel.setText(wrap(escape(m.text)));
			if (m.note != null && !m.note.isEmpty())
			{
				noteLabel.setText(wrap("💡 " + escape(m.note)));
				noteLabel.setVisible(true);
			}
			if (m.teleportHint != null && !m.teleportHint.isEmpty())
			{
				teleportLabel.setText(wrap("➤ " + escape(m.teleportHint)));
				teleportLabel.setVisible(true);
			}
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

	/** Wraps body HTML in a fixed-width html/body so the label wraps at {@link #PANEL_HTML_WIDTH}. */
	private static String wrap(String bodyHtml)
	{
		return "<html><body style='width:" + PANEL_HTML_WIDTH + "px'>" + bodyHtml + "</body></html>";
	}
}
