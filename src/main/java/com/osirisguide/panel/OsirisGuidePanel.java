/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.panel;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.GridLayout;
import javax.swing.BorderFactory;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JProgressBar;
import javax.swing.SwingUtilities;
import net.runelite.client.ui.ColorScheme;
import net.runelite.client.ui.FontManager;
import net.runelite.client.ui.PluginPanel;
import net.runelite.client.util.LinkBrowser;

/**
 * Side panel: overall progress, the current step (with requirements and manual Done/Skip),
 * a short lookahead of upcoming steps, and a reset button.
 */
public class OsirisGuidePanel extends PluginPanel
{
	private final PanelActions actions;

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

	public OsirisGuidePanel(PanelActions actions)
	{
		this.actions = actions;
		setLayout(new BorderLayout());
		setBorder(BorderFactory.createEmptyBorder(8, 8, 8, 8));

		add(buildNorth(), BorderLayout.NORTH);
		add(buildCenter(), BorderLayout.CENTER);
		add(buildSouth(), BorderLayout.SOUTH);

		wireActions();
	}

	private JPanel buildNorth()
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

	private JPanel buildCenter()
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

	private JPanel buildSouth()
	{
		JPanel south = new JPanel(new BorderLayout());
		south.setBorder(BorderFactory.createEmptyBorder(12, 0, 0, 0));
		south.add(resetButton, BorderLayout.CENTER);
		return south;
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

	/** Thread-safe: renders the given snapshot on the Swing thread. */
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

	private static String escape(String s)
	{
		if (s == null)
		{
			return "";
		}
		return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
	}
}
