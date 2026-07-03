.PHONY: up down logs status restart deploy

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

status:
	docker compose ps

restart:
	docker compose restart

deploy:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  hermes-guide Fly.io deploy"
	@echo "  See docs/deploy.md for first-deploy sequence."
	@echo "  Run: cd backend && fly deploy"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
