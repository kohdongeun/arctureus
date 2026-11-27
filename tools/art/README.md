# 아트 에셋 파이프라인

```
assets_src/raw/<카테고리>/   ← 원본 (AI 생성 이미지, 직접 그린 그림, 플레이스홀더)
        │  python tools/art/process_assets.py
        ▼
assets/images/<카테고리>/    ← 게임이 읽는 최종 PNG + manifest.json
```

| 카테고리 | 배경 제거 | 출력 규격 |
|---|---|---|
| `portraits` | O | `*_.png` 256×256 (대화창), `*_large.png` 높이 640 (컷신 상반신) |
| `backgrounds` | X | 1280×720 (꽉 채우고 가운데 잘라냄) |
| `monsters` | O | 128×128, 파일명이 `boss_`로 시작하면 256×256 |
| `ui` | O | 원본 비율 유지, 최대 1280×720 (확대하지 않음) |

## 진짜 일러스트로 교체하기

1. 생성한 이미지를 **플레이스홀더와 같은 파일명**으로 `assets_src/raw/<카테고리>/`에 덮어쓴다.
   (`.jpg`, `.webp`도 됨. 확장자가 다르면 기존 `.png` 원본은 지운다.)
2. `python tools/art/process_assets.py` 실행 (특정 카테고리만: `--only portraits`)
3. 게임 코드는 바꿀 필요 없음.

### 배경 제거가 잘 되려면
- 원본은 **균일한 단색 배경**으로 생성한다. 캐릭터에 흰색·미색이 많으면 회색(#808080)이나
  녹색(#00FF00) 배경을 쓰면 실수가 줄어든다.
- 허용치는 테두리 픽셀의 노이즈로 자동 계산된다. 배경이 덜 지워지면 `--tolerance 30`처럼 올리고,
  캐릭터가 깎이면 내린다.
- 머리카락과 목 사이처럼 **테두리와 닿지 않은 배경 구멍은 지워지지 않는다**
  (캐릭터 안쪽의 흰 옷을 보호하기 위한 의도된 동작). 그런 그림은 `--rembg`(AI 누끼,
  `pip install rembg` 필요)를 쓰거나 원본에서 직접 손본다.

## 이미지 생성 프롬프트 템플릿

공통 스타일 문구 (모든 프롬프트 앞에 붙임):

> early-2000s Korean/Japanese PC RPG illustration, cel-shaded anime style, clean ink lineart,
> soft gradient shading, steampunk medieval fantasy, brass and copper details, glowing cyan ether accents

| 파일 | 프롬프트 |
|---|---|
| `portrait_luke_{emotion}` | bust portrait of a 19-year-old young man, messy auburn hair, brass goggles on forehead, soot on cheek, old knight breastplate with steam-piston pauldrons, {emotion} expression, plain flat light gray background |
| `portrait_iris_{emotion}` | bust portrait of a 17-year-old girl, shoulder-length platinum blonde hair, teal eyes, small brass clockwork gear ornament on her head, white research coat over faded ancient-patterned cloak, {emotion} expression, plain flat gray background |
| `portrait_zed_{emotion}` | bust portrait of a 27-year-old sky pirate, long black hair tied back, telescope monocle on right eye, navy captain coat with tool pouches, small brass mechanical hawk on his shoulder, {emotion} expression, plain flat light gray background |
| `bg_chimney_ward_plaza` | isometric 2:1 quarter-view town square, lower-city industrial district, brick houses with copper chimneys and steam, cobblestone streets, cyan ether street lamps, smoky reddish dusk sky, no characters |
| `boss_rusted_claw` | monster design, rusted abandoned mining machine with two giant pincers and red glowing eyes, full body, three-quarter view, plain flat light gray background |
| `boss_grinder` | monster design, huge brass mining vehicle with spinning drill and glowing cyan ether tank, full body, three-quarter view, plain flat light gray background |
| `mon_rust_crawler` | small enemy, segmented rusted mechanical centipede, full body, plain flat light gray background |
| `mon_hollow` | small enemy, faded ghostly hooded figure made of orange-brown rust fog with glowing eyes, plain flat light gray background |
| `ui_window_menu` | ornate RPG menu window frame, riveted brass border with gear ornaments at corners, aged parchment panel inside, empty, front view, plain flat white background |
| `ui_dialogue_box` | wide RPG dialogue box, riveted brass frame, dark navy glass panel, empty, front view, plain flat white background |

`{emotion}`: normal, smile, angry, sad (+ 필요 시 surprised, serious — `data/story.json`의 `meta.emotion_tags` 참고)
