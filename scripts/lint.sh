#!/bin/bash

isort health_check.py && black -l 79 health_check.py && flake8
