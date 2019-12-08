#!/bin/bash
rm -r package/*
pipenv lock -r > requirements.txt
pip install -r requirements.txt -t ./package
rm requirements.txt
cd package
zip -r9 function.zip .
cd ${OLDPWD}/src
zip -gr9 ../package/function.zip *
cd ..
aws lambda update-function-code --function-name MessageInABottleBot --zip-file fileb://package/function.zip
