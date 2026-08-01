<?php
require __DIR__ . '/src/Tax.php';

$cases = [
    [10.00, 12.20],
    [19.99, 24.39],   // 24.3878 -> rounds to 24.39; truncation gives 24.38
    [0.05, 0.06],     // 0.061 -> 0.06
];

$failures = 0;
foreach ($cases as [$net, $expected]) {
    $got = Tax::withVat($net);
    if (abs($got - $expected) > 0.001) {
        fwrite(STDERR, "FAIL: withVat($net) = $got, expected $expected\n");
        $failures++;
    }
}
if ($failures > 0) {
    exit(1);
}
echo "OK\n";
