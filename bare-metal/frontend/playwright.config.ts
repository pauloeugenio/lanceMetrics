import {defineConfig} from '@playwright/test';
import fs from 'node:fs';
export default defineConfig({testDir:'tests',workers:1,timeout:45000,use:{baseURL:process.env.LANCE_TEST_BASE_URL||'http://127.0.0.1:8080',headless:true,launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROME || (fs.existsSync('/usr/bin/google-chrome')?'/usr/bin/google-chrome':undefined),args:['--no-sandbox']},viewport:{width:1440,height:1000}},reporter:'list'});
