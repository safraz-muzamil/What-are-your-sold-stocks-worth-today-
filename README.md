# Sold Stock Value Tracker

A small web application that helps investors estimate what previously sold Indian equity shares could be worth today.

The app reads one or more compatible broker tradebook Excel files, finds equity buy and sell transactions, fetches recent market prices, and shows a per-stock comparison between the sale value and its estimated current value.

> **Important:** This project is for educational and informational use only. It is not financial advice. Market data may be delayed, incomplete, or unavailable.

## Features

- Upload one or more compatible broker tradebook Excel files
- Filter transactions to the equity (EQ) segment
- Calculate average buy and sell prices
- Retrieve recent NSE prices through Yahoo Finance
- Account for stock splits when estimating share quantities
- Show estimated gains or losses compared with the original sale value

## Built with

- Python and Flask
- Pandas
- yfinance
- openpyxl
- HTML, CSS, and JavaScript

## Run locally

1. Clone this repository.
2. Install Python 3.
3. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the application:

   ```bash
   python app.py
   ```

5. Open `http://localhost:5000` in your browser.

## Input format

Upload a compatible broker tradebook Excel file containing fields such as symbol, trade type, segment, quantity, price, and trade date. The app currently analyzes only equity (`EQ`) transactions.

## Privacy

Avoid sharing tradebooks containing personal financial information. The application processes uploaded files during the request and this repository does not include sample customer or personal tradebook data.

## Independence

This is an independent personal developer project. It is not affiliated with, endorsed by, or sponsored by any broker, exchange, or market-data provider.

## Project status

This is an early-stage developer project, started in March 2026. Planned improvements include a clearer interface, automated tests, and deployment instructions.

## License

No license has been selected yet. Until a license is added, reuse rights are not granted automatically.
