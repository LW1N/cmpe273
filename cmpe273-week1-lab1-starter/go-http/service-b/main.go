package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"
)

var client = &http.Client{Timeout: 1 * time.Second}

func health(w http.ResponseWriter, r *http.Request) {
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func callEcho(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	msg := r.URL.Query().Get("msg")

	url := fmt.Sprintf("http://127.0.0.1:8080/echo?msg=%s", msg)
	resp, err := client.Get(url)
	if err != nil {
		log.Printf("service=B endpoint=/call-echo status=error error=%q latency_ms=%d", err.Error(), time.Since(start).Milliseconds())
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"service_b": "ok",
			"service_a": "unavailable",
			"error":     err.Error(),
		})
		return
	}
	defer resp.Body.Close()

	var data map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&data)

	log.Printf("service=B endpoint=/call-echo status=ok latency_ms=%d", time.Since(start).Milliseconds())
	_ = json.NewEncoder(w).Encode(map[string]any{
		"service_b": "ok",
		"service_a": data,
	})
}

func main() {
	http.HandleFunc("/health", health)
	http.HandleFunc("/call-echo", callEcho)
	log.Println("service=B listening on :8081")
	log.Fatal(http.ListenAndServe(":8081", nil))
}
