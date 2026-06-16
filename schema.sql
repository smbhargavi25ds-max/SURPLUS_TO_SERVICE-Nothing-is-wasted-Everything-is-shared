-- ============================================================
-- Surplus to Service — MySQL Database Setup
-- Run this file once in MySQL before starting the Flask app
-- ============================================================

CREATE DATABASE IF NOT EXISTS surplus_service
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE surplus_service;

-- Drop old tables if they exist (clean slate)
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS listings;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

-- Users table
CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(100)  NOT NULL,
  email         VARCHAR(120)  NOT NULL UNIQUE,
  password_hash VARCHAR(255)  NOT NULL,
  role          VARCHAR(50)   NOT NULL,
  is_admin      TINYINT(1)    NOT NULL DEFAULT 0,
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Listings table
CREATE TABLE listings (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  title         VARCHAR(150)  NOT NULL,
  category      VARCHAR(50)   NOT NULL,
  description   TEXT          NOT NULL,
  weight        FLOAT         NOT NULL DEFAULT 0.0,
  pickup_info   VARCHAR(200)  DEFAULT 'Available for pickup',
  status        VARCHAR(50)   NOT NULL DEFAULT 'available',
  location_name VARCHAR(100)  DEFAULT 'Main Hub',
  address       VARCHAR(200)  DEFAULT 'Default Address',
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id       INT           NOT NULL,
  CONSTRAINT fk_listings_user FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Verify tables were created
SHOW TABLES;
