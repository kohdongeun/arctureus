# 황동의 심장 : 아스카론 연대기

2000년대 초반 국산 PC RPG 감성의 2.5D 쿼터뷰 스팀펑크 판타지 RPG (pygame-ce).
현재는 프롤로그~1장 일부(굴뚝거리 → 지하 배수로 → 보스 '녹슨 집게')를 플레이할 수 있는 데모다.

## 실행

```bash
pip install -r requirements.txt
python main.py      # 2D 버전 (전투·메뉴·세이브까지 플레이 가능한 데모)
python main3d.py    # 3D 쿼터뷰 버전 (ursina, 개발 중: 필드 탐험·NPC 대화)
```

### 3D 쿼터뷰 버전 (`main3d.py`, `src3d/`)
| 키 | 동작 |
|---|---|
| WASD / 방향키 | 이동 (카메라 기준) |
| Z / Space / Enter | 대화 · 다음 대사 |
| Q / E | 카메라 45° 회전 |
| 마우스 휠 | 확대 / 축소 |

- 높이맵 지형(언덕·흙길·잔디 텍스처, 나무 그림자는 텍스처에 구움), 입체 나무·덤불·바위, 풀포기·꽃
- 항상 카메라를 바라보는 빌보드 캐릭터 + 발밑 그림자, 동료 2명이 발자취를 따라 걸음, 카메라 회전 시 앞/뒷모습 자동 전환
- 반투명 양피지 대화창 + 우측 하단 대형 스탠딩 일러스트(감정별, 인물이 바뀌면 슬라이드 인), 맵 이름 배너
- 맵 정의: `data/maps3d/*.json`, 그래픽: `python tools/art/gen_hd_chars.py`, `python tools/art/gen_textures3d.py`
- 자동 촬영 테스트: `python main3d.py --shots 폴더` (화면 없는 리눅스에서는 `xvfb-run -a` 로 실행)
- 조명은 `src3d/shaders.py` 의 자체 셰이더(방향광·환경광·안개). ursina 기본 그림자 셰이더는 일부 드라이버에서 크래시가 나서 쓰지 않는다.

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
- **세이브/로드**: 필드 메뉴(X) → 저장 (슬롯 3개, 덮어쓰기 확인), 타이틀 → 이어하기.
  저장 위치: Windows `%APPDATA%\\Arcturus_RPG\\saves`, macOS `~/Library/Application Support/Arcturus_RPG/saves`,
  Linux `~/.local/share/Arcturus_RPG/saves` (`ARCTURUS_SAVE_DIR` 로 변경 가능)
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
- 폰트: Galmuri (SIL OFL 1.1, `assets/fonts/OFL-Galmuri.md`), 나눔명조·나눔고딕 (SIL OFL 1.1, `assets/fonts/OFL-Nanum.txt`)
- 그 외 그래픽·사운드는 이 저장소의 스크립트로 생성한 것

## 실행 파일(.exe) 빌드
파이썬이 없는 PC 에서도 더블클릭으로 실행되는 단일 실행 파일을 만든다. 모든 그래픽·사운드·폰트·데이터가 포함된다.

- **자동 (권장)**: 이 저장소에 push 하면 GitHub Actions(`.github/workflows/build-windows.yml`)가 Windows 에서
  `Arcturus_RPG.exe` 를 빌드하고 실행 검증까지 한 뒤, 실행 결과 페이지의 Artifacts 에 `Arcturus_RPG-windows` 로 올린다.
- **직접 (Windows PC)**:
  ```bat
  pip install pygame-ce Pillow pyinstaller
  python tools\build_exe.py
  ```
  결과: `dist\Arcturus_RPG.exe`

PyInstaller 는 크로스 컴파일을 지원하지 않으므로 `.exe` 는 반드시 Windows 에서 빌드해야 한다
(리눅스·macOS 에서 같은 명령을 실행하면 그 OS 용 실행 파일이 나온다).
실행 중 오류가 나면 실행 파일 옆에 `Arcturus_RPG_error.log` 가 남는다.
