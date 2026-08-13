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
import java.awt.Insets;
import java.awt.Rectangle;
import javax.swing.BorderFactory;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JScrollPane;
import javax.swing.JPanel;
import javax.swing.JProgressBar;
import javax.swing.JTabbedPane;
import javax.swing.JTextArea;
import javax.swing.Scrollable;
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
	// Wrap width for the SHORT HTML labels (title/note/teleport/upcoming). Kept well under the panel's
	// usable width so they can't clip. The long step DESCRIPTION uses a JTextArea that wraps to the real
	// width instead (see textArea), so it adapts to any sidebar width with no fixed guess.
	private static final int PANEL_HTML_WIDTH = 170;

	private final PanelActions actions;

	// Guide tab
	private final JLabel progressLabel = new JLabel();
	private final JProgressBar progressBar = new JProgressBar(0, 100);
	private final JLabel sectionLabel = new JLabel();
	private final JLabel titleLabel = new JLabel();
	private final JTextArea textArea = new JTextArea();
	private final JLabel noteLabel = new JLabel();
	private final JLabel teleportLabel = new JLabel();
	private final JPanel reqContainer = new JPanel();
	private final JPanel upcomingContainer = new JPanel();
	private final JLabel upcomingHeader = new JLabel("Coming up");
	private final JButton doneButton = new JButton("Done");
	private final JButton skipButton = new JButton("Skip");
	private final JButton undoButton = new JButton("Undo");
	private final JButton wikiButton = new JButton("Wiki");
	private final JButton reportButton = new JButton("⚑ Report wrong / missing info");
	private final JButton resetButton = new JButton("Reset progress");
	private String reportBody;
	private String wikiUrl;

	// Ledger tab
	private final JLabel ledgerTotals = new JLabel();
	private final JLabel ledgerEmpty = new JLabel();
	private final JPanel ledgerRows = new JPanel();

	public GustavGuidePanel(PanelActions actions)
	{
		// wrap=false: take the FULL sidebar height instead of PluginPanel's default preferred-height
		// scroll wrapper. Without this the action row sits directly under the content (floating in the
		// middle of the panel) rather than pinned to the bottom of the page.
		super(false);
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
		JPanel center = new WidthPanel();  // fills the scroll viewport width so textArea wraps to it
		center.setLayout(new BoxLayout(center, BoxLayout.Y_AXIS));
		center.setBorder(BorderFactory.createEmptyBorder(10, 0, 0, 0));

		sectionLabel.setForeground(ColorScheme.BRAND_ORANGE);
		sectionLabel.setAlignmentX(Component.LEFT_ALIGNMENT);

		titleLabel.setFont(FontManager.getRunescapeBoldFont());
		titleLabel.setAlignmentX(Component.LEFT_ALIGNMENT);

		// Step description: a JTextArea that WRAPS TO ITS ACTUAL WIDTH (unlike a fixed-px HTML label), so
		// it fits any sidebar width and can never clip off the right edge. Non-editable, transparent,
		// styled to match the panel; a bit larger for legibility. The width-tracking center panel (below)
		// gives it the viewport width to wrap into.
		textArea.setLineWrap(true);
		textArea.setWrapStyleWord(true);
		textArea.setEditable(false);
		textArea.setOpaque(false);
		textArea.setFocusable(false);
		textArea.setBorder(null);
		textArea.setForeground(Color.LIGHT_GRAY);
		textArea.setFont(FontManager.getRunescapeFont().deriveFont(FontManager.getRunescapeFont().getSize2D() + 2f));
		textArea.setAlignmentX(Component.LEFT_ALIGNMENT);
		textArea.setMaximumSize(new Dimension(Integer.MAX_VALUE, Integer.MAX_VALUE));

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

		upcomingHeader.setFont(FontManager.getRunescapeSmallFont());
		upcomingHeader.setForeground(Color.GRAY);
		upcomingHeader.setAlignmentX(Component.LEFT_ALIGNMENT);
		upcomingHeader.setBorder(BorderFactory.createEmptyBorder(12, 0, 4, 0));

		upcomingContainer.setLayout(new BoxLayout(upcomingContainer, BoxLayout.Y_AXIS));
		upcomingContainer.setAlignmentX(Component.LEFT_ALIGNMENT);

		center.add(sectionLabel);
		center.add(titleLabel);
		center.add(textArea);
		center.add(noteLabel);
		center.add(teleportLabel);
		center.add(reqContainer);
		center.add(upcomingHeader);
		center.add(upcomingContainer);
		return center;
	}

	private JPanel buildGuideSouth()
	{
		// Action buttons live OUTSIDE the scrolling content so they stay in the SAME place at the bottom
		// of the panel no matter how long the current step's description is (inside the scroll area they
		// slid up and down with the text, and could scroll out of view entirely).
		undoButton.setToolTipText("Go back one step (reopens the previous step)");
		reportButton.setToolTipText("Tell us this step is wrong or missing something — the guide, step "
			+ "number, location and NPC/item ids are attached automatically");
		reportButton.setForeground(ColorScheme.BRAND_ORANGE);

		// Three buttons per row keeps each wide enough for its label to be readable; the report link,
		// Wiki and Reset get their own full-width rows. All of it lives in SOUTH, pinned to the bottom.
		JPanel primary = new JPanel(new GridLayout(1, 3, 4, 0));
		primary.add(doneButton);
		primary.add(skipButton);
		primary.add(undoButton);

		JPanel south = new JPanel(new GridLayout(4, 1, 0, 4));
		south.setBorder(BorderFactory.createEmptyBorder(8, 0, 0, 0));
		south.add(reportButton);   // above the action row, per the "report what & where" flow
		south.add(primary);
		south.add(wikiButton);
		south.add(resetButton);

		for (JButton b : new JButton[]{doneButton, skipButton, undoButton, wikiButton, resetButton, reportButton})
		{
			b.setFont(FontManager.getRunescapeFont());   // legible, matches the client UI
			b.setMargin(new Insets(2, 2, 2, 2));         // don't let padding squeeze the label out
			b.setFocusPainted(false);
		}
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
		// The panel takes the full sidebar height (PluginPanel(false)) and so has no outer scroll pane —
		// the ledger can list far more item rows than fit, so it needs its own, like the Guide tab.
		JScrollPane ledgerScroll = new JScrollPane(ledgerRows,
			JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED, JScrollPane.HORIZONTAL_SCROLLBAR_NEVER);
		ledgerScroll.setBorder(BorderFactory.createEmptyBorder(0, 0, 0, 0));
		ledgerScroll.getVerticalScrollBar().setUnitIncrement(16);
		tab.add(ledgerScroll, BorderLayout.CENTER);
		return tab;
	}

	private void wireActions()
	{
		doneButton.addActionListener(e -> actions.completeCurrent());
		skipButton.addActionListener(e -> actions.skipCurrent());
		undoButton.addActionListener(e -> actions.undoLast());
		reportButton.addActionListener(e -> promptAndSendReport());
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
			// developed account resuming mid-route isn't misread as "stuck on step 259". The step you
			// are actually ON is shown separately, which is what people want when comparing notes.
			String progress = m.mode + " — " + m.completed + " / " + m.total + " done";
			progressLabel.setText(m.stepNumber > 0 ? (progress + " · Step " + m.stepNumber) : progress);
		}

		reqContainer.removeAll();
		upcomingContainer.removeAll();
		this.wikiUrl = m.wikiUrl;
		this.reportBody = m.reportBody;

		boolean hasCurrent = m.loggedIn && !m.finished && !m.routeEmpty;

		noteLabel.setVisible(false);
		teleportLabel.setVisible(false);
		if (m.finished && !m.routeEmpty && m.loggedIn)
		{
			sectionLabel.setText("");
			titleLabel.setText("Route complete ✓");
			textArea.setText("You have finished the guide. Nice.");
		}
		else if (hasCurrent)
		{
			sectionLabel.setText(m.section);
			titleLabel.setText(m.title);
			textArea.setText(m.text);
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
			textArea.setText(m.routeEmpty ? "Route data is missing." : "");
		}

		doneButton.setEnabled(hasCurrent);
		skipButton.setEnabled(hasCurrent);
		// Undo stays available on a finished route (to reopen the last step), and only when something
		// has actually been completed.
		undoButton.setEnabled(m.loggedIn && !m.routeEmpty && m.completed > 0);
		reportButton.setEnabled(m.canReport && hasCurrent);
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

	/**
	 * Asks what is wrong with the current step, SHOWS the exact text that will be sent (nothing about the
	 * account is included), and sends it only if the user confirms. Everything happens on the Swing thread;
	 * the send itself is asynchronous and reports back here.
	 */
	private void promptAndSendReport()
	{
		if (reportBody == null || reportBody.isEmpty())
		{
			return;
		}
		JTextArea input = new JTextArea(4, 28);
		input.setLineWrap(true);
		input.setWrapStyleWord(true);

		JTextArea preview = new JTextArea(reportBody);
		preview.setEditable(false);
		preview.setLineWrap(true);
		preview.setWrapStyleWord(true);
		preview.setFont(FontManager.getRunescapeSmallFont());
		JScrollPane previewScroll = new JScrollPane(preview);
		previewScroll.setPreferredSize(new Dimension(360, 150));

		// Opt-in crowd-fix: standing where the step ACTUALLY happens and attaching that tile is the
		// fastest way to correct a wrong coordinate. Off by default — a report carries no position
		// unless the user ticks this for this one report.
		String tile = actions.playerTile();
		JCheckBox attachPos = new JCheckBox("Attach my position as the proposed spot"
			+ (tile != null ? " (" + tile + ")" : ""));
		attachPos.setEnabled(tile != null);

		JPanel form = new JPanel(new BorderLayout(0, 6));
		form.add(new JLabel("What's wrong with this step?"), BorderLayout.NORTH);
		form.add(new JScrollPane(input), BorderLayout.CENTER);
		JPanel south = new JPanel(new BorderLayout(0, 4));
		south.add(attachPos, BorderLayout.NORTH);
		JPanel previewBlock = new JPanel(new BorderLayout(0, 4));
		previewBlock.add(new JLabel("This will be sent (no account info):"), BorderLayout.NORTH);
		previewBlock.add(previewScroll, BorderLayout.CENTER);
		south.add(previewBlock, BorderLayout.CENTER);
		form.add(south, BorderLayout.SOUTH);

		int choice = JOptionPane.showConfirmDialog(reportButton, form, "Report this step",
			JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE);
		if (choice != JOptionPane.OK_OPTION)
		{
			return;
		}
		// Send EXACTLY what was previewed plus what was typed — not a rebuild, so a step that
		// auto-completes while the dialog is open cannot change the report behind the user's back.
		String note = input.getText();
		if (attachPos.isSelected() && tile != null)
		{
			note = (note == null ? "" : note) + "\nProposed spot (player-supplied): " + tile;
		}
		actions.reportStep(StepReport.withProblem(reportBody, note));
	}

	/** Result of a send, surfaced to the user (called from a background thread). */
	public void showReportResult(String error)
	{
		SwingUtilities.invokeLater(() -> JOptionPane.showMessageDialog(reportButton,
			error == null ? "Thanks — report sent." : error,
			error == null ? "Report sent" : "Report not sent",
			error == null ? JOptionPane.INFORMATION_MESSAGE : JOptionPane.WARNING_MESSAGE));
	}

	/**
	 * A BoxLayout panel that reports it tracks the scroll viewport's WIDTH, so its children (the
	 * wrapping step-text area) get the real available width to wrap into instead of overflowing and
	 * clipping. Height is not tracked, so tall content still scrolls vertically.
	 */
	private static final class WidthPanel extends JPanel implements Scrollable
	{
		@Override
		public Dimension getPreferredScrollableViewportSize()
		{
			return getPreferredSize();
		}

		@Override
		public int getScrollableUnitIncrement(Rectangle visible, int orientation, int direction)
		{
			return 16;
		}

		@Override
		public int getScrollableBlockIncrement(Rectangle visible, int orientation, int direction)
		{
			return visible.height;
		}

		@Override
		public boolean getScrollableTracksViewportWidth()
		{
			return true;
		}

		@Override
		public boolean getScrollableTracksViewportHeight()
		{
			return false;
		}
	}
}
