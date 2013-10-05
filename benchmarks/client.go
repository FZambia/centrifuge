package main

import (
    "code.google.com/p/go.net/websocket"
    "fmt"
    "log"
    "time"
    "os"
    "crypto/md5"
    "crypto/hmac"
    "strconv"
)

func generate_token(secret_key, project_id, user_id string) string {
    token := hmac.New(md5.New, []byte(secret_key))
    token.Write([]byte(user_id))
    token.Write([]byte(project_id))
    hex := fmt.Sprintf("%02x", token.Sum(nil))
    return hex
}

func connect(ch_sub, ch_msg, ch_start chan int, url, origin, connect_message, subscribe_message, publish_message string) {
    var err error
    var ws *websocket.Conn
    for {
        ws, err = websocket.Dial(url, "", origin)
        if err != nil {
            fmt.Println("Connection fails, is being re-connection")
            time.Sleep(1*time.Second)
            continue
        }
        break
    }
    if _, err := ws.Write([]byte(connect_message)); err != nil {
        log.Fatal(err)
    }
    var msg = make([]byte, 512)

    if _, err = ws.Read(msg); err != nil {
        log.Fatal(err)
    }
    //fmt.Printf("Received: %s.\n", msg[:n])

    if _, err := ws.Write([]byte(subscribe_message)); err != nil {
        log.Fatal(err)
    }
    if _, err = ws.Read(msg); err != nil {
        log.Fatal(err)
    }

    ch_sub <- 1

    <-ch_start

    if _, err := ws.Write([]byte(publish_message)); err != nil {
        log.Fatal(err)
    }

    for {
        if _, err = ws.Read(msg); err != nil {
            log.Fatal(err)
        }
        ch_msg <- 1
    }

}

func main() {

    origin := "http://localhost:8000/"
    url := os.Args[1]
    project_id := os.Args[2]
    project_secret := os.Args[3]
    concurrency, _ := strconv.Atoi(os.Args[4])
    clients_subscribed := 0
    messages_received := 0

    token := generate_token(project_secret, project_id, "test")

    connect_message := fmt.Sprintf("{\"params\": {\"project\": \"%s\", \"token\": \"%s\", \"user\": \"test\"}, \"method\": \"connect\"}", project_id, token)
    subscribe_message := "{\"params\": {\"namespace\": \"test\", \"channel\": \"test\"}, \"method\": \"subscribe\"}"
    publish_message := "{\"params\": {\"data\": {\"input\": \"test\"}, \"namespace\": \"test\", \"channel\": \"test\"}, \"method\": \"publish\"}"

    ch_sub := make(chan int)
    ch_msg := make(chan int)
    ch_start := make(chan int)

    for i := 0; i < concurrency; i++ {
        time.Sleep(100*time.Millisecond)
        go func() {
            connect(ch_sub, ch_msg, ch_start, url, origin, connect_message, subscribe_message, publish_message)
        }()
    }

    for {
        <-ch_sub
        clients_subscribed += 1
        if clients_subscribed == concurrency {
            fmt.Println("All clients subscribed")
            break
        }
    }

    fmt.Println("Lets go!")

    limit := concurrency*concurrency

    var start time.Time
    start = time.Now()

    for i := 0; i < concurrency; i++ {
        ch_start <- 1
    }

    for {
        <-ch_msg
        messages_received += 1
        if messages_received == limit {
            elapsed := time.Since(start)
            fmt.Printf("time: %s\n", elapsed)
            fmt.Printf("total messages: %d\n", limit)
            break
        }
    }

}