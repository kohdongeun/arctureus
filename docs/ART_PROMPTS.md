# 캐릭터 이미지 프롬프트 (무료 웹 AI 용)

무료 웹 AI(Bing Image Creator, PixAI 등)에 아래 영문 프롬프트를 그대로 붙여 넣어 생성한 뒤,
정해진 파일명으로 저장하고 명령 두 줄만 실행하면 게임에 바로 들어간다.

## 파일명 규칙

| 종류 | 저장 위치 | 파일명 | 권장 크기 |
|---|---|---|---|
| 필드 SD 캐릭터 (전신) | `assets_src/characters/field/` | `<id>.png` (예: `elwin.png`) | 1024x1024, 흰 배경 |
| 대화창 반신 일러스트 | `assets_src/characters/portrait/` | `<id>.png` (감정별은 `<id>_smile.png` 등) | 1024x1024, 흰 배경 |

- `<id>` 는 아래 목록의 영문 ID 를 그대로 쓴다. JPG/WEBP 도 된다.
- 감정 이름: normal, smile, angry, sad, surprised, serious (없으면 `<id>.png` 가 모든 감정에 쓰인다)

## 적용 명령

```bash
python tools/art/prepare_field_chars.py
python tools/art/prepare_field_chars.py --src assets_src/characters/portrait --out assets/characters/portrait
```

배경 제거(rembg) → 흰 테두리·바닥 그림자·워터마크 조각 제거 → 여백 자르기까지 자동으로 처리된다.

## 필드 SD 캐릭터 — NPC 9명 (주인공 3명은 완료)

### 1. `cecil.png` — 세실 노블

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, 19-year-old young knight captain, neat golden hair, white and gold steam-powered armor, slim ether rapier at his waist, serious proud expression, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 2. `balthazar.png` — 발타자르 그림웰

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, 58-year-old scholar, short silver hair and beard, gold-rimmed glasses, black academic coat decorated with dozens of small pocket watches, brass prosthetic left hand, calm cold expression, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 3. `morgan.png` — 마담 모르간

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, 64-year-old cheerful old woman mechanic, grey hair in a bun, leather apron over brown work clothes, brass peg leg, big wrench on her shoulder, hearty grin, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 4. `elwin.png` — 엘윈

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, young elf scout, short blonde hair, long pointed ears, green hooded tunic, brown leggings, quiver of arrows on back, energetic expression, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 5. `silvaen.png` — 대드루이드 실바엔

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, ancient elf archdruid, very long white hair, long pointed ears, flowing green and white robes with leaf embroidery, wooden staff covered in moss, kind wise expression, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 6. `torbin.png` — 강철왕 토르빈

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, stout dwarf king blacksmith, huge braided red beard, iron crown, leather smith apron over chainmail, giant forge hammer, laughing expression, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 7. `lina.png` — 리나 레이븐홀트

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, little girl with long black hair, simple white dress, holding a small brass music box, absent dreamy expression, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 8. `mirel.png` — 기억을 잃은 엘프

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, pale faded elf girl, grey hood and grey tunic, long pointed ears, faint orange glowing eyes, ghostly melancholy expression, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 9. `b7.png` — 버려진 채굴 로봇 B-7

```
anime style, 2d game character sprite, clean lineart, solid white background, cute chibi, big head small body, 3 heads tall, SD anime character, cute rusty boxy mining robot, single round cyan glowing eye, small antenna with red light, brass and rust-orange body, piston legs, full body standing with feet visible, flat cel shading, vibrant colors, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

## 대화창 반신 일러스트 — 12명

### 10. `luke.png` — 루크 애쉬포드

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, 19-year-old boy steam knight, messy auburn hair, brass goggles on forehead, soot smudge on cheek, old knight breastplate with brass steam-piston pauldrons, copper-orange jacket, dark trousers, brown boots, large piston greatsword strapped on his back, confident smile, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 11. `iris.png` — 아이리스

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, 17-year-old girl resonance mage, shoulder-length platinum blonde hair, teal eyes, small brass clockwork gear hair ornament, white research coat with cyan trim over a faded teal cloak with ancient patterns, teal skirt, white stockings, holding a tuning-fork staff, curious gentle expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 12. `zed.png` — 제드 레이븐홀트

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, 27-year-old sky pirate sniper, long black hair tied in a low ponytail, telescope monocle on right eye, long navy captain coat with brass buttons and tool pouches, long ether rifle on his back, small brass mechanical hawk perched on his shoulder, relaxed smirk, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 13. `cecil.png` — 세실 노블

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, 19-year-old young knight captain, neat golden hair, white and gold steam-powered armor, slim ether rapier at his waist, serious proud expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 14. `balthazar.png` — 발타자르 그림웰

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, 58-year-old scholar, short silver hair and beard, gold-rimmed glasses, black academic coat decorated with dozens of small pocket watches, brass prosthetic left hand, calm cold expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 15. `morgan.png` — 마담 모르간

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, 64-year-old cheerful old woman mechanic, grey hair in a bun, leather apron over brown work clothes, brass peg leg, big wrench on her shoulder, hearty grin, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 16. `elwin.png` — 엘윈

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, young elf scout, short blonde hair, long pointed ears, green hooded tunic, brown leggings, quiver of arrows on back, energetic expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 17. `silvaen.png` — 대드루이드 실바엔

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, ancient elf archdruid, very long white hair, long pointed ears, flowing green and white robes with leaf embroidery, wooden staff covered in moss, kind wise expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 18. `torbin.png` — 강철왕 토르빈

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, stout dwarf king blacksmith, huge braided red beard, iron crown, leather smith apron over chainmail, giant forge hammer, laughing expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 19. `lina.png` — 리나 레이븐홀트

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, little girl with long black hair, simple white dress, holding a small brass music box, absent dreamy expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 20. `mirel.png` — 기억을 잃은 엘프

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, pale faded elf girl, grey hood and grey tunic, long pointed ears, faint orange glowing eyes, ghostly melancholy expression, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```

### 21. `b7.png` — 버려진 채굴 로봇 B-7

```
anime style, 2d game character sprite, clean lineart, solid white background, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, cute rusty boxy mining robot, single round cyan glowing eye, small antenna with red light, brass and rust-orange body, piston legs, soft cel shading, facing slightly left, isolated on plain white, simple background, no scenery, no shapes behind, no text
```
