package main

import (
    "code.google.com/p/go.net/websocket"
    "fmt"
    "log"
    "time"
    "os"
    "crypto/sha256"
    "crypto/hmac"
    "strconv"
)

func generate_token(secret_key, project_key, user_id string, timestamp string) string {
    token := hmac.New(sha256.New, []byte(secret_key))
    token.Write([]byte(project_key))
    token.Write([]byte(user_id))
    token.Write([]byte(timestamp))
    hex := fmt.Sprintf("%02x", token.Sum(nil))
    return hex
}

func subscriber(ch_sub, ch_start chan int, url, origin, connect_message, subscribe_message, publish_message string) {
    var err error
    var ws *websocket.Conn
    for {
        ws, err = websocket.Dial(url, "", origin)
        if err != nil {
            //fmt.Println("Connection fails, is being re-connection")
            time.Sleep(10*time.Millisecond)
            continue
        }
        break
    }
    if _, err := ws.Write([]byte(connect_message)); err != nil {
        fmt.Println("subscriber connect write error")
        log.Fatal(err)
    }
    var msg = make([]byte, 512)

    if _, err = ws.Read(msg); err != nil {
        fmt.Println("subscriber connect read error")
        log.Fatal(err)
    }
    //fmt.Printf("Received: %s.\n", msg[:n])

    if _, err := ws.Write([]byte(subscribe_message)); err != nil {
        fmt.Println("subscriber subscribe write error")
        log.Fatal(err)
    }
    if _, err = ws.Read(msg); err != nil {
        fmt.Println("subscriber subscribe read error")
        log.Fatal(err)
    }

    ch_sub <- 1

    for {
        if _, err = ws.Read(msg); err != nil {
            fmt.Println("subscriber msg read error")
            log.Fatal(err)
        }
        fmt.Println("message received")
    }

}

func main() {

    origin := "http://localhost:8000/"
    url := os.Args[1]
    project_key := os.Args[2]
    project_secret := os.Args[3]
    timestamp := strconv.FormatInt(time.Now().Unix(), 10)
    fmt.Println(timestamp)
    max_clients, _ := strconv.Atoi(os.Args[4])

    fmt.Printf("max clients: %d\n", max_clients)

    token := generate_token(project_secret, project_key, "test", timestamp)

    connect_message := fmt.Sprintf("{\"params\": {\"project\": \"%s\", \"timestamp\": \"%s\", \"token\": \"%s\", \"user\": \"test\"}, \"method\": \"connect\"}", project_key, timestamp, token)
    subscribe_message := "{\"params\": {\"channel\": \"test\"}, \"method\": \"subscribe\"}"
    publish_message := "{\"params\": {\"data\": {\"input\": \"I am benchmarking Centrifuge at moment\"}, \"channel\": \"test\"}, \"method\": \"publish\"}"

    ch_sub := make(chan int)
    ch_start := make(chan int)

    for i := 0; i < max_clients; i ++ {

        time.Sleep(5*time.Millisecond)

        go func() {
            subscriber(ch_sub, ch_start, url, origin, connect_message, subscribe_message, publish_message)
        }()

        <-ch_sub

        fmt.Printf("%d clients subscribed\n", i+1)
    }

    for {
        time.Sleep(time.Second)
    }

}