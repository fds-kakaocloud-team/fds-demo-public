# FDS 모의 거래 탐지

FastAPI 및 Random Forest 기반 모의 이체와 이상 거래 탐지 시연 프로젝트입니다. 학습된 모델은 `models/`에 포함되어 있으며 서버에서는 로드하여 추론합니다. 실제 금융 거래나 결제망에 연결되지 않습니다.

## 실행

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 5000
```

`http://127.0.0.1:5000/`에서 시연하고 `/health`에서 상태를 확인합니다. 기본 저장소는 SQLite이며 실제 환경변수를 설정하면 MySQL과 S3 호환 감사 저장소를 이용할 수 있습니다. `deploy/fds.env.example`은 예시이며 실제 설정과 비밀번호, 인증 파일을 Git에 저장하지 마세요. 테이블 SQL과 systemd 예시는 `deploy/`에 있습니다.

학습 및 테스트는 PC에서 `pip install -r requirements-dev.txt` 후 진행합니다. `python -m unittest discover -s tests -v`를 이용하세요. 자동 생성 테스트 입력과 모델별 판정은 `docs/detection-criteria.md`, 테스트 사례는 `docs/demo-scenarios.md`를 참고하세요. 이 시연 앱에는 사용자 인증이 없으므로 접근 범위를 제한해야 합니다.

## 데이터 출처

PaySim 모델은 Edgar Alonso Lopez-Rojas 등이 만든 [PaySim 공개 합성 데이터](https://www.kaggle.com/datasets/ntnu-testimon/paysim1)로 학습했습니다. 데이터는 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)에 따라 제공됩니다. 데이터 원본은 포함하지 않습니다. 시간·거리 모델은 자체 생성한 합성 데이터로 학습했습니다. 두 모델을 결합한 정책의 성능은 검증되지 않았습니다.

## 배포 업데이트

공개 저장소를 각 WAS에 복제하고 가상환경을 준비합니다. 서버별 배포는 LB에서 제외 후 `fds-api`와 `fds-audit-worker`를 중지하고 `deploy/update.sh`를 실행합니다. 이 스크립트는 `git pull --ff-only`, 의존성 설치, 모델 로드를 수행합니다. 서비스 시작과 헬스체크, 감사 업로드 확인 및 LB 복귀는 담당자와 조율하여 별도로 수행합니다. 기존 Flask 포트를 자동으로 중지하지 않습니다. GitHub에 변경을 올려도 WAS는 자동 업데이트되지 않으며 각 서버에서 스크립트를 실행해야 합니다.
