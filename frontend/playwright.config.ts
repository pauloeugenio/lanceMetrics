import {defineConfig} from '@playwright/test';
import fs from 'node:fs';
export default defineConfig({testDir:'tests',timeout:45000,use:{baseURL:'http://127.0.0.1:8080',headless:true,launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROME || (fs.existsSync('/usr/bin/google-chrome')?'/usr/bin/google-chrome':undefined),args:['--no-sandbox']},viewport:{width:1440,height:1000}},reporter:'list'});
