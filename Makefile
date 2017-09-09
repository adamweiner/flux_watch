max_line_length := 110

PHONY: reqs
reqs:
	pip3 install --upgrade -r flux_watch/requirements.txt -t ./flux_watch/

.PHONY: pep8
pep8:
	pep8 flux_watch/flux_watch.py --max-line-length=$(max_line_length)

.PHONY: pylint
pylint:
	pylint flux_watch/flux_watch.py --rcfile ./.pylintrc --max-line-length=$(max_line_length)

.PHONY: check
check: pep8 pylint

.PHONY: run
run:
	python3 flux_watch/flux_watch.py

.PHONY: clean
clean:
	rm -f flux_watch.zip

.PHONY: plan
plan:
	cd terraform && terraform plan -out saved-plan

.PHONY: apply
apply:
	cd terraform && terraform apply saved-plan && mv -f saved-plan saved-plan.applied

.PHONY: destroy
destroy:
	cd terraform && terraform destroy

.PHONY: zip
zip:
	cd flux_watch && zip -r flux_watch.zip * && mv -f flux_watch.zip ../flux_watch.zip

.PHONY: deploy
deploy: zip plan apply
