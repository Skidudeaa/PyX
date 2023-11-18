

struct ContentView: View {
    @State var songData: Song? = loadAndParseJSON()
    @State var currentLyrics: [String] = ["Starting..."]
    @State var currentAnnotations: [String] = ["Starting..."]
    @State var currentIndex: Int = 0
    @State var elapsedTime: Float = 0.0
    @State var offset: CGFloat = 0
    @State var annotationDisplayTime: Double = 0.0
    @State var displayAnnotation: Bool = false
    
    let timer = Timer.publish(every: 0.1, on: .main, in: .common).autoconnect()

    var body: some View {
        ZStack {
            Color(UIColor.fromHex(songData?.bgColor ?? ""))
                .ignoresSafeArea() // Fills the whole screen
            
            VStack {
                // Your custom TitleView
                if let song = songData {
                    TitleView(song: song, textColor: Color(UIColor.fromHex(song.textColors.textColor4 ?? "")))
                }
                
                // Your custom ProgressView
                ProgressView(currentTime: $elapsedTime, songDuration: songDuration, fillColor: Color(UIColor.fromHex(songData?.textColors.textColor3 ?? "")))
                
                ScrollViewReader { proxy in
                    ScrollView {
                        ForEach(0..<currentLyrics.count, id: \.self) { index in
                            VStack(alignment: .leading) {
                                if displayAnnotation && index == currentIndex - 1 {
                                    Text(currentAnnotations[index])
                                        .foregroundColor(Color(UIColor.fromHex(songData?.textColors.textColor2 ?? "")))
                                        .font(.system(size: 16, weight: .light))
                                        .padding(.bottom, 10)
                                        .transition(.move(edge: .top))
                                        .animation(.easeInOut(duration: 1.0), value: displayAnnotation)
                                }
                                Text(currentLyrics[index])
                                    .foregroundColor(Color(UIColor.fromHex(songData?.textColors.textColor1 ?? "")))
                            }
                            .id(index)
                        }
                    }
                    .onAppear {
                        if currentIndex > 2 {
                            proxy.scrollTo(currentIndex - 2, anchor: .center)
                        } else {
                            proxy.scrollTo(0, anchor: .center)
                        }
                    }
                }
            }
        }
        .onReceive(timer) { _ in
            updateLyrics()
        }
    }
    
    func updateLyrics() {
        guard let songData = songData else { return }
        
        if currentIndex < songData.lyrics_and_annotations.count {
            let currentLyricData = songData.lyrics_and_annotations[currentIndex]
            
            if elapsedTime >= currentLyricData.timestamp {
                currentLyrics.append(currentLyricData.lyric)
                currentAnnotations.append(currentLyricData.annotation ?? "No annotation")
                
                displayAnnotation = false
                annotationDisplayTime = Double(currentLyricData.annotation?.components(separatedBy: " ").count ?? 0) * 0.5
                
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                    withAnimation {
                        displayAnnotation = true
                    }
                }
                
                DispatchQueue.main.asyncAfter(deadline: .now() + annotationDisplayTime + 1.0) {
                    withAnimation {
                        displayAnnotation = false
                    }
                }
                
                currentIndex += 1
            }
            
            elapsedTime += 0.1
        } else {
            timer.upstream.connect().cancel()
        }
    }
}