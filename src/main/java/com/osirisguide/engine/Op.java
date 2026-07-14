/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

/**
 * Numeric comparison operator used by skill/varbit/varp/quest-point conditions.
 */
public enum Op
{
	GE(">="),
	LE("<="),
	GT(">"),
	LT("<"),
	EQ("=");

	private final String symbol;

	Op(String symbol)
	{
		this.symbol = symbol;
	}

	public boolean test(int actual, int target)
	{
		switch (this)
		{
			case GE:
				return actual >= target;
			case LE:
				return actual <= target;
			case GT:
				return actual > target;
			case LT:
				return actual < target;
			case EQ:
			default:
				return actual == target;
		}
	}

	public String getSymbol()
	{
		return symbol;
	}

	/**
	 * Parses an operator from a JSON string, defaulting to {@link #GE} (the common
	 * "reach at least this level/value" case) when absent or unrecognised.
	 */
	public static Op fromString(String s)
	{
		if (s == null)
		{
			return GE;
		}
		switch (s.trim())
		{
			case ">=":
			case "ge":
				return GE;
			case "<=":
			case "le":
				return LE;
			case ">":
			case "gt":
				return GT;
			case "<":
			case "lt":
				return LT;
			case "=":
			case "==":
			case "eq":
				return EQ;
			default:
				return GE;
		}
	}
}
