package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"sync"
	"time"
)

type Node struct {
	NodeID    string  `json:"node_id"`
	Service   string  `json:"service"`
	Healthy   bool    `json:"healthy"`
	ActiveConns int   `json:"active_connections"`
	BaseLatency float64 `json:"base_latency_ms"`
}

type RouteRequest struct {
	Source      string `json:"source"`
	Destination string `json:"destination"`
	Algorithm   string `json:"algorithm"`
}

type Span struct {
	Service    string  `json:"service"`
	Node       string  `json:"node"`
	DurationMs float64 `json:"duration_ms"`
	Status     string  `json:"status"`
}

type RouteResponse struct {
	SelectedNode string  `json:"selected_node"`
	DurationMs   float64 `json:"duration_ms"`
	Status       string  `json:"status"`
	Algorithm    string  `json:"algorithm"`
	Span         Span    `json:"span"`
}

var (
	nodes   = make(map[string]*Node)
	nodesMu sync.RWMutex
	rrIndex = make(map[string]int)
	rrMu    sync.Mutex
)

func getServiceNodes(service string) []*Node {
	nodesMu.RLock()
	defer nodesMu.RUnlock()
	var result []*Node
	for _, n := range nodes {
		if n.Service == service && n.Healthy {
			result = append(result, n)
		}
	}
	return result
}

func pickNode(service, algorithm string) *Node {
	candidates := getServiceNodes(service)
	if len(candidates) == 0 {
		return nil
	}

	switch algorithm {
	case "least_connections":
		best := candidates[0]
		for _, n := range candidates[1:] {
			if n.ActiveConns < best.ActiveConns {
				best = n
			}
		}
		return best
	case "random":
		return candidates[rand.Intn(len(candidates))]
	default:
		rrMu.Lock()
		idx := rrIndex[service] % len(candidates)
		rrIndex[service]++
		rrMu.Unlock()
		return candidates[idx]
	}
}

func handleSync(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var incoming []Node
	if err := json.NewDecoder(r.Body).Decode(&incoming); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	nodesMu.Lock()
	nodes = make(map[string]*Node)
	for i := range incoming {
		n := incoming[i]
		nodes[n.NodeID] = &n
	}
	nodesMu.Unlock()
	w.WriteHeader(http.StatusOK)
	fmt.Fprintln(w, "synced")
}

func handleRoute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req RouteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	target := pickNode(req.Destination, req.Algorithm)
	if target == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(RouteResponse{Status: "no_healthy_nodes"})
		return
	}

	nodesMu.Lock()
	target.ActiveConns++
	nodesMu.Unlock()

	start := time.Now()
	jitter := (rand.Float64()*2 - 0.5) * 10
	sleepMs := target.BaseLatency + jitter
	if sleepMs < 1 {
		sleepMs = 1
	}
	time.Sleep(time.Duration(sleepMs) * time.Millisecond)

	nodesMu.Lock()
	target.ActiveConns--
	nodesMu.Unlock()

	durationMs := float64(time.Since(start).Microseconds()) / 1000.0
	status := "ok"
	if rand.Float64() < 0.05 {
		status = "error"
	}

	resp := RouteResponse{
		SelectedNode: target.NodeID,
		DurationMs:   durationMs,
		Status:       status,
		Algorithm:    req.Algorithm,
		Span: Span{
			Service:    req.Destination,
			Node:       target.NodeID,
			DurationMs: durationMs,
			Status:     status,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintln(w, "ok")
}

func main() {
	rand.Seed(time.Now().UnixNano())
	http.HandleFunc("/route", handleRoute)
	http.HandleFunc("/sync", handleSync)
	http.HandleFunc("/health", handleHealth)
	log.Println("Go data plane listening on :8001")
	log.Fatal(http.ListenAndServe(":8001", nil))
}