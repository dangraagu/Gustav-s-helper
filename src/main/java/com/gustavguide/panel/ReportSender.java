/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.panel;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.function.Consumer;
import javax.inject.Inject;
import javax.inject.Singleton;
import lombok.extern.slf4j.Slf4j;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * Sends a step report to the configured endpoint (a Discord webhook, or a forwarding endpoint that holds
 * the webhook privately — the URL is the only difference).
 *
 * <p>Only ever fires from an explicit user click, never automatically. The request is asynchronous so the
 * client thread and the UI are never blocked, and a failure is reported back to the panel rather than
 * thrown — a broken endpoint must not disturb the game.</p>
 */
@Slf4j
@Singleton
public class ReportSender
{
	private static final MediaType JSON = MediaType.parse("application/json");
	/** Cheap anti-spam: one report per this interval, per client. */
	private static final Duration MIN_INTERVAL = Duration.ofSeconds(20);

	private final OkHttpClient httpClient;   // provided by RuneLite — no extra dependency is shipped
	private volatile Instant lastSent = Instant.EPOCH;

	@Inject
	public ReportSender(OkHttpClient httpClient)
	{
		this.httpClient = httpClient;
	}

	/** @return true if a report may be sent now (rate limit not tripped). */
	public boolean canSend()
	{
		return Duration.between(lastSent, Instant.now()).compareTo(MIN_INTERVAL) >= 0;
	}

	/**
	 * POST the report. {@code onResult} is called with null on success or a short human-readable reason
	 * on failure; it may be invoked on a background thread, so the caller marshals to Swing itself.
	 */
	public void send(String endpoint, String body, Consumer<String> onResult)
	{
		if (endpoint == null || endpoint.trim().isEmpty())
		{
			onResult.accept("No report endpoint is configured.");
			return;
		}
		if (!canSend())
		{
			onResult.accept("Please wait a moment before sending another report.");
			return;
		}
		lastSent = Instant.now();

		// An explicit User-Agent is required, not cosmetic: Discord sits behind Cloudflare, which rejects
		// a POST with a missing/generic agent (HTTP 403, error 1010) — verified against the live endpoint.
		Request request;
		try
		{
			request = buildRequest(endpoint, body);
		}
		catch (IllegalArgumentException badUrl)
		{
			// A hand-typed endpoint in the config can be anything; report it instead of failing silently.
			onResult.accept("That report endpoint isn't a valid URL.");
			return;
		}
		httpClient.newCall(request).enqueue(callback(onResult));
	}

	private Request buildRequest(String endpoint, String body)
	{
		return new Request.Builder()
			.url(endpoint.trim())
			.header("User-Agent", "GustavsHelper (+https://github.com/dangraagu/Gustav-s-helper)")
			.post(RequestBody.create(JSON, StepReport.discordPayload(body)))
			.build();
	}

	private Callback callback(Consumer<String> onResult)
	{
		return new Callback()
		{
			@Override
			public void onFailure(Call call, IOException e)
			{
				log.debug("Gustav's Helper: step report failed", e);
				onResult.accept("Could not reach the report service. Check your connection.");
			}

			@Override
			public void onResponse(Call call, Response response)
			{
				try (Response r = response)
				{
					if (r.isSuccessful())
					{
						onResult.accept(null);
					}
					else
					{
						log.debug("Gustav's Helper: step report rejected, HTTP {}", r.code());
						onResult.accept("The report service rejected the report (HTTP " + r.code() + ").");
					}
				}
			}
		};
	}
}
