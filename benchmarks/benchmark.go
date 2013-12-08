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
    token.Write([]byte(project_id))
    token.Write([]byte(user_id))
    hex := fmt.Sprintf("%02x", token.Sum(nil))
    return hex
}

func publisher(ch_trigger chan int, ch_time chan time.Time, url, origin, connect_message, subscribe_message, publish_message string) {
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

    var msg = make([]byte, 512)

    if _, err := ws.Write([]byte(connect_message)); err != nil {
        log.Fatal(err)
    }
    if _, err = ws.Read(msg); err != nil {
        log.Fatal(err)
    }

    if _, err := ws.Write([]byte(subscribe_message)); err != nil {
        log.Fatal(err)
    }
    if _, err = ws.Read(msg); err != nil {
        log.Fatal(err)
    }

    for {
        <-ch_trigger

        if _, err := ws.Write([]byte(publish_message)); err != nil {
            log.Fatal(err)
        }

        ch_time <- time.Now()

        if _, err = ws.Read(msg); err != nil {
            log.Fatal(err)
        }

        if _, err = ws.Read(msg); err != nil {
            log.Fatal(err)
        }

    }
}

func subscriber(ch_sub, ch_msg, ch_start chan int, url, origin, connect_message, subscribe_message, publish_message string) {
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

    for {
        if _, err = ws.Read(msg); err != nil {
            log.Fatal(err)
        }
        //fmt.Println("message received")
        ch_msg <- 1
    }

}

func main() {

    origin := "http://localhost:8000/"
    url := os.Args[1]
    project_id := os.Args[2]
    project_secret := os.Args[3]
    concurrency, _ := strconv.Atoi(os.Args[4])
    messages_received := 0

    token := generate_token(project_secret, project_id, "test")

    connect_message := fmt.Sprintf("{\"params\": {\"project\": \"%s\", \"token\": \"%s\", \"user\": \"test\"}, \"method\": \"connect\"}", project_id, token)
    subscribe_message := "{\"params\": {\"namespace\": \"test\", \"channel\": \"test\"}, \"method\": \"subscribe\"}"
    publish_message := "{\"params\": {\"data\": {\"input\": \"I am benchmarking Centrifuge at moment\"}, \"namespace\": \"test\", \"channel\": \"test\"}, \"method\": \"publish\"}"

    ch_sub := make(chan int)
    ch_msg := make(chan int)
    ch_start := make(chan int)
    ch_trigger := make(chan int)
    ch_time := make(chan time.Time)

    var start_time time.Time

    repeats := 100

    total_time := 0.0

    go func() {
        publisher(ch_trigger, ch_time, url, origin, connect_message, subscribe_message, publish_message)
    }()

    for i := 0; i < concurrency; i++ {

        time.Sleep(500*time.Millisecond)

        total_time = 0

        go func() {
            subscriber(ch_sub, ch_msg, ch_start, url, origin, connect_message, subscribe_message, publish_message)
        }()

        <-ch_sub

        //fmt.Println("one more client connected, total connected")

        // repeat several times to get average time value
        for k := 0; k < repeats; k++ {

            time.Sleep(100*time.Millisecond)

            messages_received = 0

            // publish message
            //fmt.Println("publishing message")
            ch_trigger <- 1

            start_time = <-ch_time

            for {
                <-ch_msg
                messages_received += 1
                //fmt.Println(messages_received)
                if messages_received == i + 1 {
                    elapsed := time.Since(start_time)
                    //fmt.Printf("time: %s\n", elapsed)
                    //fmt.Println(float64(elapsed))
                    total_time += float64(elapsed)
                    break
                }
            }
        }

        fmt.Printf("%d %f\n", i + 1, total_time/float64(repeats))

    }

}