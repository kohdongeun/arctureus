# 황동의 심장 : 아스카론 연대기

2000년대 초반 국산 PC RPG 감성의 2.5D 쿼터뷰 스팀펑크 판타지 RPG (pygame-ce).
현재는 프롤로그~1장 일부(굴뚝거리 → 지하 배수로 → 보스 '녹슨 집게')를 플레이할 수 있는 데모다.

## 실행

```bash
pip install -r requirements.txt
python main.py
```

| 키 | 동작 |
|---|---|
| 방향키 / WASD | 이동 (↑ 북동, → 남동, ↓ 남서, ← 북서) · 메뉴 커서 |
| Z / Enter / Space | 대화 · 조사 · 결정 |
| X / Esc | 취소 · 필드 메뉴 |

## 구현된 시스템
- **필드**: 아이소메트릭 타일맵, 블록을 쌓은 건물, 깊이 정렬, 에테르 가로등 광원, 어두운 맵 조명, 맵 이동, NPC 배회
- **대화**: 타자기 효과, 감정별 초상화 일러스트(주인공), NPC 는 도트 초상화, 대사는 `data/story.json` 에서 읽음
- **ATB 전투**: 속도 기반 게이지, 웨이트 모드 명령 입력(공격/스킬/방어/아이템/도주), 약점·내성·치명타,
  상태이상(화상·정지·실명·도발·방어↑·약점노출), 루크 증기압 게이지(MAX 시 1.5배 → 다음 턴 과열), 보스 폭주 패턴
- **이펙트**: 가산 합성 파티클·링·빔·빛기둥·시계 정지 등 스킬별 연출, 대미지 숫자, 피격 흔들림
- **성장**: 경험치, 레벨업(능력치 상승·스킬 습득 표시), 결과 화면
- **사운드**: 직접 작곡·합성한 BGM 4곡(마을/배수로/전투/승리, `.mid` 동봉)과 효과음 21종

## 폴더
```
main.py                 진입점
src/engine              게임 루프·장면 스택·입력, 리소스 로더·오디오
src/scenes              title / field / dialogue / battle / menu
src/entities/party.py   캐릭터·레벨업·인벤토리
src/systems/effects.py  스킬 이펙트
src/ui/widgets.py       9-slice 창, 게이지, 톱니 커서, 목록 메뉴
data/story.json         세계관·인물·스토리·NPC 대사·아트 방향
data/battle.json        전투 수치·적·인카운트·아이템
data/maps/*.json        맵 (바닥 영역, 건물, 소품, NPC, 출구, 인카운트, 보스)
tools/art               도트 그래픽 생성 / 일러스트 후처리(누끼·리사이즈)
tools/audio             BGM·효과음 합성
tools/autotest.py       자동 플레이 테스트
```

## 에셋 다시 만들기
```bash
python tools/art/gen_pixel_art.py      # 캐릭터 스프라이트·타일·블록·소품
python tools/art/process_assets.py     # assets_src/raw 의 일러스트 → assets/images
python tools/audio/gen_audio.py        # BGM(.wav + .mid)·효과음
```

## 테스트
```bash
python tools/autotest.py               # 화면 없이 타이틀~보스까지 자동 플레이, saves/autotest/ 에 스크린샷
```

## 라이선스 메모
- 폰트: Galmuri (SIL OFL 1.1, `assets/fonts/OFL-Galmuri.md`)
- 그 외 그래픽·사운드는 이 저장소의 스크립트로 생성한 것
