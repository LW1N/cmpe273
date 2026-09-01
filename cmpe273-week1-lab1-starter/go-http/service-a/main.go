package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

func health(w http.ResponseWriter, r *http.Request) {
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func echo(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	msg := r.URL.Query().Get("msg")
	_ = json.NewEncoder(w).Encode(map[string]string{"echo": msg})
	log.Printf("service=A endpoint=/echo status=ok latency_ms=%d", time.Since(start).Milliseconds())
}

func main() {
	http.HandleFunc("/health", health)
	http.HandleFunc("/echo", echo)
	log.Println("service=A listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
