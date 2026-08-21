// src/modules/auth/auth.routes.js
const express = require('express');
const controller = require('./auth.controller');

const router = express.Router();

router.get('/login', controller.loginForm);
router.post('/login', controller.login);
router.get('/registro', controller.registroForm);
router.post('/registro', controller.registro);
router.post('/logout', controller.logout);

module.exports = router;
