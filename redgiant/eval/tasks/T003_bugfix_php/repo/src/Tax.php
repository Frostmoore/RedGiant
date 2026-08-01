<?php

class Tax
{
    public const VAT = 22.0; // percent

    public static function withVat(float $net): float
    {
        // BUG: integer cast truncates cents instead of rounding
        return (float) (int) ($net * (1 + self::VAT / 100) * 100) / 100;
    }
}
