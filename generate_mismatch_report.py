"""
JSUT コーパスの kana_level3（正解読み）と pyopenjtalk の出力（カタカナ読み）の不一致を、
人間が読みやすいテキストファイルとして出力する。

出力:
1. mismatch_report_jsut.txt - 全不一致件
2. mismatch_report_jsut_summary.md - サマリー

正規化ルール（ROHAN 版と同一）:
- エ段+い → エ段+え（読み形/発音形の長音表記ゆれ）
- オ段+う → オ段+お（同上）
- づ→ず、ぢ→じ（同一音素）
- を→お
- 長音「ー」を直前の母音に展開
- 句読点・無声化記号除去
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

try:
    import pyopenjtalk
except ImportError:
    pyopenjtalk = None

# ---------------------------------------------------------------------------
# パス定義
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
YAML_PATH = BASE_DIR / 'text_kana' / 'basic5000.yaml'
REPORT_PATH = BASE_DIR / 'mismatch_report_jsut.txt'
SUMMARY_PATH = BASE_DIR / 'mismatch_report_jsut_summary.md'

# ---------------------------------------------------------------------------
# 長音展開用マッピング（ひらがな版）
# ---------------------------------------------------------------------------
VOWEL_MAP: dict[str, str] = {
    'あ': 'あ', 'い': 'い', 'う': 'う', 'え': 'え', 'お': 'お',
    'ぁ': 'あ', 'ぃ': 'い', 'ぅ': 'う', 'ぇ': 'え', 'ぉ': 'お',
    'ゃ': 'あ', 'ゅ': 'う', 'ょ': 'お',
    'か': 'あ', 'き': 'い', 'く': 'う', 'け': 'え', 'こ': 'お',
    'が': 'あ', 'ぎ': 'い', 'ぐ': 'う', 'げ': 'え', 'ご': 'お',
    'さ': 'あ', 'し': 'い', 'す': 'う', 'せ': 'え', 'そ': 'お',
    'ざ': 'あ', 'じ': 'い', 'ず': 'う', 'ぜ': 'え', 'ぞ': 'お',
    'た': 'あ', 'ち': 'い', 'つ': 'う', 'て': 'え', 'と': 'お',
    'だ': 'あ', 'ぢ': 'い', 'づ': 'う', 'で': 'え', 'ど': 'お',
    'な': 'あ', 'に': 'い', 'ぬ': 'う', 'ね': 'え', 'の': 'お',
    'は': 'あ', 'ひ': 'い', 'ふ': 'う', 'へ': 'え', 'ほ': 'お',
    'ば': 'あ', 'び': 'い', 'ぶ': 'う', 'べ': 'え', 'ぼ': 'お',
    'ぱ': 'あ', 'ぴ': 'い', 'ぷ': 'う', 'ぺ': 'え', 'ぽ': 'お',
    'ま': 'あ', 'み': 'い', 'む': 'う', 'め': 'え', 'も': 'お',
    'や': 'あ', 'ゆ': 'う', 'よ': 'お',
    'ら': 'あ', 'り': 'い', 'る': 'う', 'れ': 'え', 'ろ': 'お',
    'わ': 'あ', 'ゐ': 'い', 'ゑ': 'え', 'を': 'お',
    'ん': 'ん', 'っ': 'っ', 'ゔ': 'う',
}


def normalize_for_comparison(kana: str) -> str:
    """
    比較用にひらがな文字列を正規化する。

    句読点除去、を→お、づ→ず、ぢ→じ、長音展開、読み/発音形の統一。

    Args:
        kana (str): ひらがな文字列

    Returns:
        str: 正規化後の文字列
    """

    # 句読点・記号・アクセント記号除去
    cleaned = re.sub(r'[、。？！?!\s\u0027\u2018\u2019\u02bc]', '', kana)
    # づ→ず, ぢ→じ
    # 注意: を→お は長音正規化の後に行う（を+う語頭の誤正規化を防ぐため）
    cleaned = cleaned.replace('づ', 'ず').replace('ぢ', 'じ')
    # 長音展開
    result: list[str] = []
    for char in cleaned:
        if char == 'ー':
            if len(result) > 0:
                expanded = VOWEL_MAP.get(result[-1], 'あ')
                result.append(expanded)
            else:
                result.append('あ')
        else:
            result.append(char)
    # 長音の読み形→発音形の正規化（え段+い→え段+え、お段+う→お段+お）
    # ただし直前が「を」の場合は長音ではないためスキップ
    # （「を+う語頭単語」は長音ではなく別の単語の先頭）
    for index in range(1, len(result)):
        prev_char = result[index - 1]
        current_char = result[index]
        if prev_char == 'を':
            continue
        prev_vowel = VOWEL_MAP.get(prev_char)
        if current_char == 'い' and prev_vowel == 'え':
            result[index] = 'え'
        elif current_char == 'う' and prev_vowel == 'お':
            result[index] = 'お'
    # を→お は長音正規化の後に行う
    return ''.join(result).replace('を', 'お')


def kata_to_hira(kata: str) -> str:
    """
    カタカナをひらがなに変換する。

    Args:
        kata (str): カタカナ文字列

    Returns:
        str: ひらがな文字列
    """

    result: list[str] = []
    for char in kata:
        code_point = ord(char)
        # カタカナ（ァ～ヶ）→ ひらがな
        if 0x30A1 <= code_point <= 0x30F6:
            result.append(chr(code_point - 0x60))
        elif char == 'ヴ':
            result.append('ゔ')
        else:
            result.append(char)
    return ''.join(result)


def get_pyopenjtalk_reading(text: str) -> str | None:
    """
    pyopenjtalk でテキストの発音を取得し、ひらがなで返す。

    Args:
        text (str): 入力テキスト

    Returns:
        str | None: ひらがな読み、または取得失敗時は None
    """

    if pyopenjtalk is None:
        return None
    try:
        nodes = pyopenjtalk.run_frontend(text)
        if nodes is None:
            return None
        prons = [node.get('pron', '') for node in nodes if node.get('pron') and node.get('pron') != '、']
        if len(prons) == 0:
            return None
        return kata_to_hira(''.join(prons))
    except Exception:
        return None


def levenshtein_distance(str_a: str, str_b: str) -> int:
    """
    2つの文字列間のレーベンシュタイン距離を計算する。

    Args:
        str_a (str): 文字列 A
        str_b (str): 文字列 B

    Returns:
        int: レーベンシュタイン距離
    """

    len_a = len(str_a)
    len_b = len(str_b)
    dp = [[0] * (len_b + 1) for _ in range(len_a + 1)]
    for i in range(len_a + 1):
        dp[i][0] = i
    for j in range(len_b + 1):
        dp[0][j] = j
    for i in range(1, len_a + 1):
        for j in range(1, len_b + 1):
            cost = 0 if str_a[i - 1] == str_b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[len_a][len_b]


def generate_diff_description(norm_truth: str, norm_pyojt: str) -> list[str]:
    """
    正規化後の2文字列の差分を人間が読みやすい形で記述する。

    Args:
        norm_truth (str): 正解の正規化文字列
        norm_pyojt (str): pyopenjtalk の正規化文字列

    Returns:
        list[str]: 差分記述のリスト
    """

    diffs: list[str] = []
    min_len = min(len(norm_truth), len(norm_pyojt))
    for i in range(min_len):
        if norm_truth[i] != norm_pyojt[i]:
            diffs.append(f'    {i + 1}文字目: {norm_pyojt[i]}→{norm_truth[i]}')
    if len(norm_truth) > len(norm_pyojt):
        diffs.append(f'    正解が {len(norm_truth) - len(norm_pyojt)} 文字長い')
    elif len(norm_pyojt) > len(norm_truth):
        diffs.append(f'    pyopenjtalk が {len(norm_pyojt) - len(norm_truth)} 文字長い')
    return diffs


def main() -> None:
    """
    メインエントリーポイント。

    JSUT の kana_level3 と pyopenjtalk 出力を比較し、ミスマッチレポートを生成する。
    """

    if pyopenjtalk is None:
        print('Error: pyopenjtalk is not installed', file=sys.stderr)
        return

    # YAML 読み込み
    if YAML_PATH.exists() is not True:
        print(f'Error: YAML not found: {YAML_PATH}', file=sys.stderr)
        return

    print(f'Loading YAML: {YAML_PATH}')
    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    print(f'Loaded entries: {len(data)}')

    # 全エントリを処理
    total = 0
    mismatch_count = 0
    report_lines: list[str] = []
    distance_counts: dict[int, int] = {}

    for entry_key in sorted(data.keys()):
        entry = data[entry_key]
        text = entry.get('text_level2', entry.get('text_level0', ''))
        kana_truth = entry.get('kana_level3', entry.get('kana_level0', ''))

        if not text or not kana_truth:
            continue

        total += 1

        # pyopenjtalk の読みを取得
        pyojt_kana = get_pyopenjtalk_reading(text)
        if pyojt_kana is None:
            continue

        # 正規化して比較
        truth_norm = normalize_for_comparison(kana_truth)
        pyojt_norm = normalize_for_comparison(pyojt_kana)

        if truth_norm == pyojt_norm:
            continue

        mismatch_count += 1
        distance = levenshtein_distance(truth_norm, pyojt_norm)
        distance_counts[distance] = distance_counts.get(distance, 0) + 1

        # レポートエントリ生成
        diffs = generate_diff_description(truth_norm, pyojt_norm)

        report_lines.append('=' * 72)
        report_lines.append(f'#{mismatch_count:04d}: {entry_key}')
        report_lines.append('=' * 72)
        report_lines.append(f'テキスト: {text}')
        report_lines.append('')
        report_lines.append(f'正解 (kana_level3):  {kana_truth}')
        report_lines.append(f'                     (正規化後: {truth_norm})')
        report_lines.append('')
        report_lines.append(f'pyopenjtalk 出力:    {pyojt_kana}')
        report_lines.append(f'                     (正規化後: {pyojt_norm})')
        report_lines.append('')
        report_lines.append(f'距離: {distance}')
        report_lines.append('')
        if len(diffs) > 0:
            report_lines.append('差分 (pyopenjtalk → 正解、正規化後):')
            report_lines.extend(diffs)
        report_lines.append('')

    # レポート出力
    print(f'Total entries: {total}')
    print(f'Mismatches: {mismatch_count}')

    REPORT_PATH.write_text('\n'.join(report_lines), encoding='utf-8')
    print(f'Saved: {REPORT_PATH}')

    # サマリー出力
    summary_lines: list[str] = []
    summary_lines.append('# JSUT ミスマッチレポート サマリー')
    summary_lines.append('')
    summary_lines.append(f'- 全エントリ数: {total}')
    summary_lines.append(f'- 不一致件数: {mismatch_count} ({mismatch_count / total * 100:.1f}%)')
    summary_lines.append(f'- 一致件数: {total - mismatch_count} ({(total - mismatch_count) / total * 100:.1f}%)')
    summary_lines.append('')
    summary_lines.append('## 距離分布')
    summary_lines.append('')
    summary_lines.append('| 距離 | 件数 | 割合 |')
    summary_lines.append('|---:|---:|---:|')
    for dist in sorted(distance_counts.keys()):
        count = distance_counts[dist]
        summary_lines.append(f'| {dist} | {count} | {count / mismatch_count * 100:.1f}% |')
    summary_lines.append('')

    SUMMARY_PATH.write_text('\n'.join(summary_lines), encoding='utf-8')
    print(f'Saved: {SUMMARY_PATH}')


if __name__ == '__main__':
    main()
