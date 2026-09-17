<?php
/**
 * MigrationExperiment - run the legacy body and the new backend call in the same
 * request, compare the two results, and hand the page the legacy one.
 *
 * WHERE THIS FILE GOES
 *   Copy it next to the migration switch helper - the directory named by
 *   `legacy.switch.helperPath` in workspace.json - and require it from the swap
 *   wrapper. It is a template: it carries no paths, hosts, table names or page
 *   names, so it can live in the public OS repository and be copied into the
 *   legacy tree unchanged.
 *
 *   require_once dirname(__FILE__) . '/MigrationExperiment.php';
 *
 * HOW A SWAP USES IT
 *   $data = MigrationExperiment::run(
 *       '<experiment-name>',               // appears in every log line
 *       '<TOGGLE_ENV_VAR>',                // the switch helper's env var for this page
 *       $control,                          // control: the legacy body, as a closure
 *       $candidate,                        // candidate: the new backend call
 *       array('total'),                    // keys excluded from the equal verdict
 *       array('input' => $params, 'page' => __FILE__)
 *   );
 *
 *   Both callables take no arguments and return the value the page binds. Close
 *   over what they need. In PHP 5.3+ that is a closure:
 *       $control = function () use ($params) { return legacy_body($params); };
 *
 * MODES (read with getenv, strict compare, unknown value means legacy)
 *   legacy     control only. Nothing is logged. This is the default and the value
 *              of every string that is not one of the two below - unset, empty,
 *              a typo, different case. There is no value that routes to the new
 *              backend by accident.
 *   dual       both run, in random order; the results are compared; the MISMATCH
 *              is appended to a JSONL log; the CONTROL value is returned. A page
 *              in dual mode behaves exactly as it did before.
 *   migrated   candidate only. Exceptions propagate, as they do in production.
 *
 *   getenv() and not $_SERVER: two runtimes serve this docroot and $_SERVER is
 *   absent under one of them, which would lock that runtime to legacy forever with
 *   no error and no failing test. The switch helper carries the measurement.
 *
 * TWO INSTRUMENTATION VARIABLES ON TOP OF THE MODES (set by `pagecheck`, never by hand)
 *   NOISE_ENV non-empty     legacy vs legacy. The control runs twice and is compared
 *                           against itself, the log line is marked `noise`, and the
 *                           control value is returned. The toggle stays `legacy`, so
 *                           the page is exactly as it was. This measures the
 *                           RUN-TO-RUN DIFFERENCE: the diff keys that move between two
 *                           runs of the same code (clocks, session tokens, another team
 *                           writing rows). Without it, an equivalence loop cannot tell
 *                           its own jitter from a missing rule, and the cheapest way to
 *                           close the loop becomes ignoring keys until it is quiet.
 *   FAKEVALUE_ENV non-empty Only in `migrated`. The control still RUNS - every side
 *                           effect it has happens exactly as before - but its return
 *                           value is thrown away and replaced by the marker, and the
 *                           candidate's value is what the page binds. The capture taken
 *                           must then be BYTE-IDENTICAL to the migrated baseline.
 *                           Two different leaks turn that red: a wrapper or page that
 *                           still derives a rendered value from the control's return
 *                           (it renders the marker), and a legacy body that writes
 *                           screen state as a side effect (it runs here and did not in
 *                           the baseline, so the screen moves). What it cannot see is a
 *                           side effect that is byte-identical to what the candidate
 *                           produces; that one belongs to the executed-lines check.
 *                           The legacy body is not edited, so its recorded body hash
 *                           holds - `pagecheck` re-checks that hash in the same stage.
 *
 * WHY THE CANDIDATE'S EXCEPTIONS ARE SWALLOWED IN DUAL MODE
 *   The new path is designed to fail loudly rather than fall back, because a silent
 *   fallback returns 200 with an empty list and paints a failure green. Dual mode
 *   inverts that on purpose and only there: an experiment must never change what the
 *   user sees. The exception is recorded in the log line as `candidate_error`, so it
 *   is louder in the report than it would have been in a stack trace nobody reads.
 *
 * WHAT THE LOG IS FOR
 *   `dualrun-report` reads it. One JSON object per line, appended under LOCK_EX, at
 *   the path in the MIGRATION_EXPERIMENT_LOG environment variable. No path, no log,
 *   and the helper says so once on stderr rather than failing quietly - an empty log
 *   and "the toggle never reached PHP" look identical otherwise.
 *
 * ENCODING
 *   Equality is decided on raw bytes, never on decoded text. This tree mixes CP949
 *   and UTF-8 per file, so a helper that transcoded before comparing would report two
 *   different byte strings as equal and hide the exact bug that renders as mojibake.
 *   The log line is JSON and JSON must be valid UTF-8, so strings that are not valid
 *   UTF-8 are transcoded for the log only, and the line is marked `recoded` to say the
 *   payload is a view rather than the bytes. The shas are always over the raw bytes.
 *
 * PHP 5.6. No scalar type hints, no return types, no ?? operator, no arrow functions.
 * Pure ASCII: the legacy tree holds files in two encodings and a comment in one of
 * them would corrupt on the first edit by a tool that assumes the other.
 */
class MigrationExperiment
{
    /** Must equal legacy.switch.values.dual / .migrated in workspace.json. */
    const VALUE_DUAL = 'dual';
    const VALUE_MIGRATED = 'spring';

    /** Must equal legacy.dualRun.logEnvVar in workspace.json. */
    const LOG_ENV = 'MIGRATION_EXPERIMENT_LOG';

    /**
     * Must equal legacy.dualRun.noiseEnvVar / .fakeValueEnvVar in workspace.json.
     * Only `pagecheck` sets these, and it clears them again in the same stage.
     * Both are OFF for every value that is unset or empty - the same fail-safe
     * shape as the toggle, for the same reason: an instrumentation variable left set by
     * accident must not be able to change what a page returns.
     */
    const NOISE_ENV = 'MIGRATION_EXPERIMENT_NOISE';
    const FAKEVALUE_ENV = 'MIGRATION_EXPERIMENT_FAKEVALUE';

    const MAX_LINE = 65536;
    const MAX_DEPTH = 32;

    private static $warned = false;

    /**
     * Returns the value the page should bind. Never returns the candidate's value
     * unless the mode is migrated.
     */
    public static function run($name, $envVar, $control, $candidate,
                               $ignoreKeys = array(), $context = array())
    {
        $mode = self::mode($envVar);

        // Run-to-run difference. Deliberately ahead of the mode dispatch: the toggle must stay
        // `legacy` while it is measured, and `legacy` returns before reaching dual().
        $noise = self::env(self::NOISE_ENV);
        if ($noise !== null) {
            $context['noise'] = true;
            return self::dual($name, $control, $control, $ignoreKeys, $context);
        }

        if ($mode === 'legacy') {
            return call_user_func($control);
        }
        if ($mode === 'migrated') {
            $fakevalue = self::env(self::FAKEVALUE_ENV);
            if ($fakevalue !== null) {
                return self::faked($name, $control, $candidate, $fakevalue, $context);
            }
            return call_user_func($candidate);
        }
        return self::dual($name, $control, $candidate, $ignoreKeys, $context);
    }

    /** An env var's value, or null when it is unset or empty. */
    private static function env($name)
    {
        $raw = getenv($name);
        if ($raw === false || $raw === '') {
            return null;
        }
        return $raw;
    }

    // ---------------------------------------------------------------- fakevalue

    /**
     * Run the control for its side effects, discard its return value, and hand the
     * page the candidate's. Returns the candidate - fakevalue never reaches the screen
     * through this function's return; it reaches it only if something ELSE on the
     * page is still deriving a rendered value from the control's return.
     */
    private static function faked($name, $control, $candidate, $marker, $context)
    {
        $ran = true;
        $discarded = null;
        try {
            // The return value is read and then dropped on purpose. What the page
            // gets in its place is fakeValue($marker) wherever anything still
            // substitutes for it; here it gets the candidate's value instead.
            $discarded = self::ser(call_user_func($control), 0);
        } catch (Exception $e) {
            $ran = false;                  // the body throwing is itself a result to record
        } catch (Throwable $e) {
            $ran = false;
        }
        $candidateValue = call_user_func($candidate);
        try {
            $rec = array(
                'ts' => date('c'),
                'experiment' => $name,
                'mode' => 'migrated',
                'fakevalue' => $marker,
                'control_ran' => $ran,
                'discarded_sha' => ($discarded === null
                    ? null : hash('sha256', $discarded)),
                'equal' => true,
                'diff_keys' => array(),
                'ignored_keys' => array(),
                'truncated' => false,
                'input' => isset($context['input']) ? $context['input'] : null,
                'page' => self::page($context),
                'caller' => self::caller(),
            );
            self::write($rec);
        } catch (Exception $e) {
            self::warn('log failed: ' . $e->getMessage());
        } catch (Throwable $e) {
            self::warn('log failed: ' . $e->getMessage());
        }
        return $candidateValue;
    }

    /**
     * The value that stands in for the legacy body's return. Public so a swap wrapper
     * that legitimately has to substitute deeper than this function can use the same
     * marker - the capture comparison looks for these bytes and nothing else.
     */
    public static function fakeValue($marker)
    {
        return 'FAKEVALUE:' . $marker;
    }

    /**
     * 'legacy' | 'dual' | 'migrated'. Public so the toggle readback page can print
     * what the application actually sees rather than what the compose file says.
     */
    public static function mode($envVar)
    {
        $raw = getenv($envVar);
        if ($raw === self::VALUE_DUAL) {
            return 'dual';
        }
        if ($raw === self::VALUE_MIGRATED) {
            return 'migrated';
        }
        return 'legacy';
    }

    // ------------------------------------------------------------------ dual

    private static function dual($name, $control, $candidate, $ignoreKeys, $context)
    {
        $first = (mt_rand(0, 1) === 1);

        $controlValue = null;
        $candidateValue = null;
        $controlMs = 0;
        $candidateMs = 0;
        $error = null;

        if ($first) {
            $t = microtime(true);
            $controlValue = call_user_func($control);
            $controlMs = (int) round((microtime(true) - $t) * 1000);
        }

        $t = microtime(true);
        try {
            $candidateValue = call_user_func($candidate);
        } catch (Exception $e) {
            $error = array('class' => get_class($e), 'message' => $e->getMessage());
        } catch (Throwable $e) {
            $error = array('class' => get_class($e), 'message' => $e->getMessage());
        }
        $candidateMs = (int) round((microtime(true) - $t) * 1000);

        if (!$first) {
            $t = microtime(true);
            $controlValue = call_user_func($control);
            $controlMs = (int) round((microtime(true) - $t) * 1000);
        }

        // Recording must not be able to change what the page renders.
        try {
            self::record($name, $controlValue, $candidateValue, $error, $ignoreKeys,
                         $context, $controlMs, $candidateMs, $first);
        } catch (Exception $e) {
            self::warn('log failed: ' . $e->getMessage());
        } catch (Throwable $e) {
            self::warn('log failed: ' . $e->getMessage());
        }

        return $controlValue;
    }

    private static function record($name, $controlValue, $candidateValue, $error,
                                   $ignoreKeys, $context, $controlMs, $candidateMs,
                                   $controlFirst)
    {
        $controlSer = self::ser($controlValue, 0);
        if ($error === null) {
            $candidateSer = self::ser($candidateValue, 0);
            $diff = self::diffKeys($controlValue, $candidateValue, '', 0);
        } else {
            $candidateSer = null;
            $diff = array();
        }

        $ignored = array();
        $remaining = array();
        foreach ($diff as $key) {
            if (self::isIgnored($key, $ignoreKeys)) {
                $ignored[] = $key;
            } else {
                $remaining[] = $key;
            }
        }
        $equal = ($error === null && count($remaining) === 0);

        $rec = array(
            'ts' => date('c'),
            'experiment' => $name,
            'mode' => 'dual',
            'input' => isset($context['input']) ? $context['input'] : null,
            'control_sha' => hash('sha256', $controlSer),
            'candidate_sha' => ($candidateSer === null
                ? null : hash('sha256', $candidateSer)),
            'equal' => $equal,
            'diff_keys' => $diff,
            'ignored_keys' => $ignored,
            'ignored' => (count($ignored) > 0),
            'truncated' => false,
            'control_ms' => $controlMs,
            'candidate_ms' => $candidateMs,
            'control_first' => $controlFirst,
            'page' => self::page($context),
            'caller' => self::caller(),
        );
        if ($error !== null) {
            $rec['candidate_error'] = $error;
        }
        if (isset($context['note'])) {
            $rec['note'] = $context['note'];
        }
        $extra = $context;
        unset($extra['input'], $extra['page'], $extra['note']);
        if (count($extra) > 0) {
            $rec['context'] = $extra;
        }
        // Equal rows carry no payload. The counts stay exact - the report needs them
        // to say "118 equal, 2 not" - and the log stays small enough to keep.
        if (!$equal) {
            $rec['control'] = $controlValue;
            $rec['candidate'] = $candidateValue;
        }
        self::write($rec);
    }

    private static function write($rec)
    {
        $path = getenv(self::LOG_ENV);
        if ($path === false || $path === '') {
            self::warn('no ' . self::LOG_ENV . ' in the environment; dual-run '
                . 'comparisons are being computed and thrown away. Mount a log path '
                . 'into the container, or an empty report will read as "no mismatches".');
            return;
        }

        $line = self::encode($rec);
        if ($line === null) {
            return;
        }
        if (strlen($line) > self::MAX_LINE) {
            unset($rec['control'], $rec['candidate']);
            $rec['truncated'] = true;
            $line = self::encode($rec);
            if ($line !== null && strlen($line) > self::MAX_LINE) {
                $rec['input'] = array('sha256' => hash('sha256', self::ser(
                    isset($rec['input']) ? $rec['input'] : null, 0)));
                $line = self::encode($rec);
            }
        }
        if ($line === null) {
            return;
        }
        $ok = @file_put_contents($path, $line . "\n", FILE_APPEND | LOCK_EX);
        if ($ok === false) {
            self::warn('cannot append to ' . $path . '; the report will be reading a '
                . 'log that is missing lines.');
        }
    }

    private static function encode($rec)
    {
        $safe = self::jsonSafe($rec, 0, $recoded);
        if ($recoded) {
            $safe['recoded'] = true;
        }
        $line = json_encode($safe);
        if ($line === false) {
            self::warn('json_encode failed (' . json_last_error() . '); line dropped.');
            return null;
        }
        return $line;
    }

    // ------------------------------------------------------- comparison

    /**
     * Canonical byte serialization. Maps are key-sorted, lists keep their order,
     * every scalar carries its type, strings carry their raw bytes and length. Two
     * values are equal exactly when these strings are equal.
     */
    private static function ser($v, $depth)
    {
        if ($depth > self::MAX_DEPTH) {
            return 'X';
        }
        if (is_object($v)) {
            return 'O' . self::ser(self::toArray($v), $depth + 1);
        }
        if (is_array($v)) {
            $isList = self::isList($v);
            if (!$isList) {
                ksort($v, SORT_STRING);
            }
            $parts = array();
            foreach ($v as $k => $item) {
                $head = $isList ? '' : ('S' . strlen((string) $k) . ':' . $k . '=');
                $parts[] = $head . self::ser($item, $depth + 1);
            }
            return ($isList ? 'L[' : 'M[') . implode(',', $parts) . ']';
        }
        if ($v === null) {
            return 'N';
        }
        if (is_bool($v)) {
            return $v ? 'T' : 'F';
        }
        if (is_int($v)) {
            return 'I' . $v;
        }
        if (is_float($v)) {
            if (is_nan($v)) {
                return 'DNAN';
            }
            if (is_infinite($v)) {
                return $v > 0 ? 'DINF' : 'D-INF';
            }
            return 'D' . sprintf('%.17G', $v);
        }
        if (is_resource($v)) {
            return 'R';
        }
        return 'S' . strlen($v) . ':' . $v;
    }

    /**
     * Every path where the two values differ. Array indexes are part of the path
     * (`items[0].title`), so a mismatch names the row, not just the column.
     */
    private static function diffKeys($a, $b, $prefix, $depth)
    {
        if ($depth > self::MAX_DEPTH) {
            return array();
        }
        if (is_object($a)) {
            $a = self::toArray($a);
        }
        if (is_object($b)) {
            $b = self::toArray($b);
        }
        if (is_array($a) && is_array($b)) {
            $out = array();
            $keys = array_keys($a);
            foreach (array_keys($b) as $k) {
                if (!in_array($k, $keys, true)) {
                    $keys[] = $k;
                }
            }
            foreach ($keys as $k) {
                $path = is_int($k)
                    ? $prefix . '[' . $k . ']'
                    : ($prefix === '' ? (string) $k : $prefix . '.' . $k);
                $hasA = array_key_exists($k, $a);
                $hasB = array_key_exists($k, $b);
                if (!$hasA || !$hasB) {
                    $out[] = $path;
                    continue;
                }
                $out = array_merge($out, self::diffKeys($a[$k], $b[$k], $path, $depth + 1));
            }
            return $out;
        }
        if (self::ser($a, $depth) === self::ser($b, $depth)) {
            return array();
        }
        return array($prefix === '' ? '<root>' : $prefix);
    }

    /**
     * `total` covers `total` and everything under it; `items[].title` covers
     * `items[0].title`. Same rule the report applies to ignore.json, so a key that
     * is expected here is expected there.
     */
    private static function isIgnored($diffKey, $ignoreKeys)
    {
        if (!is_array($ignoreKeys)) {
            return false;
        }
        foreach ($ignoreKeys as $rule) {
            if (!is_string($rule) || $rule === '') {
                continue;
            }
            if ($rule === $diffKey) {
                return true;
            }
            if (strpos($diffKey, $rule . '.') === 0 || strpos($diffKey, $rule . '[') === 0) {
                return true;
            }
            if (strpos($rule, '[]') !== false || strpos($rule, '[*]') !== false) {
                $rx = preg_quote($rule, '/');
                $rx = str_replace(array('\[\]', '\[\*\]'), '\[\d+\]', $rx);
                if (preg_match('/^' . $rx . '([.\[].*)?$/', $diffKey) === 1) {
                    return true;
                }
            }
        }
        return false;
    }

    // ------------------------------------------------------------ helpers

    private static function isList($a)
    {
        $i = 0;
        // array_keys(), not `as $k => $unused`: the discarded value was a real
        // unused variable, and a template that ships with a lint warning is a
        // template every copy of it carries.
        foreach (array_keys($a) as $k) {
            if ($k !== $i) {
                return false;
            }
            $i++;
        }
        return true;
    }

    private static function toArray($obj)
    {
        $vars = get_object_vars($obj);
        return is_array($vars) ? $vars : array();
    }

    /** UTF-8 clean copy for the log line. Sets $recoded when anything was converted. */
    private static function jsonSafe($v, $depth, &$recoded)
    {
        if (!isset($recoded)) {
            $recoded = false;
        }
        if ($depth > self::MAX_DEPTH) {
            return '<depth>';
        }
        if (is_object($v)) {
            $v = self::toArray($v);
        }
        if (is_array($v)) {
            $out = array();
            foreach ($v as $k => $item) {
                $key = is_string($k) ? self::utf8($k, $recoded) : $k;
                $out[$key] = self::jsonSafe($item, $depth + 1, $recoded);
            }
            return $out;
        }
        if (is_resource($v)) {
            return '<resource>';
        }
        if (is_float($v) && (is_nan($v) || is_infinite($v))) {
            return (string) $v;
        }
        if (is_string($v)) {
            return self::utf8($v, $recoded);
        }
        return $v;
    }

    private static function utf8($s, &$recoded)
    {
        if (preg_match('//u', $s) === 1) {
            return $s;
        }
        $recoded = true;
        if (function_exists('iconv')) {
            $out = @iconv('CP949', 'UTF-8//IGNORE', $s);
            if ($out !== false && $out !== '') {
                return $out;
            }
        }
        if (function_exists('mb_convert_encoding')) {
            $out = @mb_convert_encoding($s, 'UTF-8', 'CP949');
            if ($out !== '' && preg_match('//u', $out) === 1) {
                return $out;
            }
        }
        return 'base64:' . base64_encode($s);
    }

    private static function page($context)
    {
        if (isset($context['page'])) {
            return $context['page'];
        }
        if (isset($_SERVER['SCRIPT_NAME'])) {
            return $_SERVER['SCRIPT_NAME'];
        }
        return null;
    }

    /**
     * file:line of whoever called run(). The same DAO method is called with opposite
     * paging semantics from different pages, so a log without the caller erases the
     * difference between two call sites that disagree.
     */
    private static function caller()
    {
        $stack = debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS, 4);
        foreach ($stack as $frame) {
            if (isset($frame['file']) && basename($frame['file']) !== basename(__FILE__)) {
                return basename($frame['file']) . ':'
                    . (isset($frame['line']) ? $frame['line'] : '?');
            }
        }
        return null;
    }

    /** Once per request. A warning on every call would itself become the incident. */
    private static function warn($message)
    {
        if (self::$warned) {
            return;
        }
        self::$warned = true;
        $text = 'MigrationExperiment: ' . $message . "\n";
        if (@file_put_contents('php://stderr', $text) === false) {
            error_log(rtrim($text));
        }
    }
}
