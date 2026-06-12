#!/usr/bin/env bash
#
# xiaohu-video-translate 一键安装脚本
# 把技能复制到 Claude/Codex 的 skills 目录，并从模板生成 config.json
#
# 用法：
#   bash install.sh
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_DIR/skills"
SKILLS_DSTS=("$HOME/.claude/skills" "$HOME/.codex/skills")

SKILLS=(xiaohu-video-download xiaohu-video-md xiaohu-subtitle-polish xiaohu-media-translate)

ffmpeg_has_subtitle_filters() {
  local bin="$1"
  local filters
  filters="$("$bin" -hide_banner -filters 2>/dev/null || true)"
  [[ "$filters" == *" ass "* || "$filters" == *" subtitles "* ]]
}

for SKILLS_DST in "${SKILLS_DSTS[@]}"; do
  echo "==> 安装目标：$SKILLS_DST"
  mkdir -p "$SKILLS_DST"

  for s in "${SKILLS[@]}"; do
    echo "==> 复制技能：$s"
    rm -rf "$SKILLS_DST/$s"
    cp -R "$SKILLS_SRC/$s" "$SKILLS_DST/$s"

    # 从模板生成 config.json（已存在则不覆盖，保护用户已有配置）
    example="$SKILLS_DST/$s/config.example.json"
    config="$SKILLS_DST/$s/config.json"
    if [ -f "$example" ] && [ ! -f "$config" ]; then
      cp "$example" "$config"
      echo "    已生成 config.json（请按需修改 output_dir）"
    fi
  done
done

echo ""
echo "==> 检查命令行依赖"
missing=()
for bin in yt-dlp ffmpeg; do
  if command -v "$bin" >/dev/null 2>&1; then
    echo "    [OK] $bin"
  else
    echo "    [缺] $bin"
    missing+=("$bin")
  fi
done

if command -v ffmpeg >/dev/null 2>&1; then
  if ffmpeg_has_subtitle_filters ffmpeg; then
    echo "    [OK] ffmpeg 字幕烧录滤镜"
  elif [ -x "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" ] && ffmpeg_has_subtitle_filters /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg; then
    echo "    [OK] ffmpeg-full 字幕烧录滤镜（脚本会自动优先使用）"
  else
    echo "    [缺] ffmpeg 缺少 ass/subtitles 滤镜；音频合成字幕视频和烧录字幕需要 ffmpeg-full/libass"
    echo "         macOS 可尝试：brew install ffmpeg-full"
  fi
fi

# whisper-cli 是可选备份转写引擎，缺了不影响默认流程（默认走 mlx/faster，模型自动下载）
if command -v whisper-cli >/dev/null 2>&1; then
  echo "    [OK] whisper-cli（可选备份引擎）"
else
  echo "    [--] whisper-cli 未装（可选备份引擎，默认走 mlx/faster，不需要它）"
fi

if [ "${#missing[@]}" -gt 0 ]; then
  echo ""
  case "$(uname -s)" in
    Darwin) echo "缺少依赖，用 Homebrew 安装：    brew install ${missing[*]}" ;;
    Linux)  echo "缺少依赖（示例）：              sudo apt install ffmpeg && pip3 install yt-dlp" ;;
    *)      echo "缺少依赖：${missing[*]}（Windows 建议用 WSL，或用 winget / pip 安装）" ;;
  esac
fi

echo ""
echo "==> 检查 Python 转写引擎（任选其一即可）"
if python3 -c "import mlx_whisper" 2>/dev/null; then
  echo "    [OK] mlx-whisper（Apple Silicon Metal GPU 加速，首选）"
elif python3 -c "import faster_whisper" 2>/dev/null; then
  echo "    [OK] faster-whisper（CPU 兜底）"
else
  echo "    [缺] 两个都没有，建议安装其一："
  echo "         pip3 install --break-system-packages mlx-whisper      # Apple Silicon"
  echo "         pip3 install --break-system-packages faster-whisper   # 通用"
fi

echo ""
echo "==> 完成。重启 Claude Code 或 Codex 后，对它说「把这个 YouTube 链接翻译成中文字幕视频」即可。"
echo "    每个技能的输出目录在 ~/.claude/skills/<技能名>/config.json 或 ~/.codex/skills/<技能名>/config.json 里改。"
