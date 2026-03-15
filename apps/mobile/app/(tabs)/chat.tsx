/**
 * 채팅 탭 — RAG Q&A
 */
import { useEffect, useRef, useState } from 'react';
import {
  Animated,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { Colors } from '@/constants/Colors';
import { LoadingIndicator } from '@/components/ui/LoadingIndicator';
import { useAuthStore } from '@/store/authStore';
import api from '@/lib/api';

interface ChatMessage {
  role:      'user' | 'assistant';
  content:   string;
  createdAt: string;
}

interface ChatHistoryResponse {
  data: ChatMessage[];
  meta: { nextCursor: string | null };
}

// ---- Animated typing indicator (3 dots) ----
function TypingIndicator() {
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const makePulse = (dot: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(dot, { toValue: 1, duration: 300, useNativeDriver: true }),
          Animated.timing(dot, { toValue: 0, duration: 300, useNativeDriver: true }),
          Animated.delay(600 - delay),
        ]),
      );

    const anim = Animated.parallel([
      makePulse(dot1, 0),
      makePulse(dot2, 150),
      makePulse(dot3, 300),
    ]);
    anim.start();
    return () => anim.stop();
  }, [dot1, dot2, dot3]);

  const dotStyle = (anim: Animated.Value) => ({
    opacity: anim,
    transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [0, -4] }) }],
  });

  return (
    <View style={[typingStyles.bubble]}>
      <View style={typingStyles.dots}>
        <Animated.View style={[typingStyles.dot, dotStyle(dot1)]} />
        <Animated.View style={[typingStyles.dot, dotStyle(dot2)]} />
        <Animated.View style={[typingStyles.dot, dotStyle(dot3)]} />
      </View>
    </View>
  );
}

const typingStyles = StyleSheet.create({
  bubble: {
    alignSelf:       'flex-start',
    backgroundColor: Colors.surface,
    borderWidth:     1,
    borderColor:     Colors.border,
    borderRadius:    16,
    borderBottomLeftRadius: 4,
    padding:         12,
    marginVertical:  2,
  },
  dots:   { flexDirection: 'row', gap: 5, alignItems: 'center', height: 20 },
  dot:    { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.textSecondary },
});

// ---- Main screen ----
export default function ChatScreen() {
  const { t } = useTranslation();
  const { languageCode } = useAuthStore();
  const scrollRef = useRef<ScrollView>(null);

  // noticeId param: 공지 상세에서 '더 물어보기' 버튼으로 진입 시
  const { noticeId } = useLocalSearchParams<{ noticeId?: string }>();

  const [message,       setMessage]       = useState('');
  const [sessionId,     setSessionId]     = useState<string | undefined>(undefined);
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
  const [chipsVisible,  setChipsVisible]  = useState(true);

  // 공지 컨텍스트 진입 시 채팅 배너 안내
  const hasNoticeContext = Boolean(noticeId);

  // 이력 조회
  const { data: historyData, isLoading } = useQuery<ChatHistoryResponse>({
    queryKey: ['chatHistory'],
    queryFn:  () => api.get('/chat/history').then((r) => r.data),
    staleTime: 60 * 1000,
  });

  // 메시지 전송
  const sendMutation = useMutation({
    mutationFn: async (text: string) => {
      const payload: Record<string, unknown> = {
        message: text,
        sessionId,
        langCode: languageCode,
      };
      if (noticeId) payload.noticeId = noticeId;

      const { data } = await api.post<{
        data: { answer: string; sessionId: string; sources: unknown[] };
      }>('/chat', payload);
      return data.data;
    },
    onMutate: (text) => {
      setChipsVisible(false);
      const userMsg: ChatMessage = { role: 'user', content: text, createdAt: new Date().toISOString() };
      setLocalMessages((prev) => [...prev, userMsg]);
    },
    onSuccess: (result) => {
      setSessionId(result.sessionId);
      const assistantMsg: ChatMessage = {
        role: 'assistant', content: result.answer, createdAt: new Date().toISOString(),
      };
      setLocalMessages((prev) => [...prev, assistantMsg]);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    },
  });

  async function handleSend(text?: string) {
    const body = (text ?? message).trim();
    if (!body || sendMutation.isPending) return;
    setMessage('');
    sendMutation.mutate(body);
  }

  const historyMessages = (historyData?.data ?? []).slice().reverse();
  const allMessages = [...historyMessages, ...localMessages];
  const isEmpty = allMessages.length === 0 && !sendMutation.isPending;

  if (isLoading) return <LoadingIndicator fullScreen />;

  const quickQuestions = [
    t('chat.quickQuestion1'),
    t('chat.quickQuestion2'),
    t('chat.quickQuestion3'),
  ];

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      {/* 공지 컨텍스트 배너 */}
      {hasNoticeContext && (
        <View style={styles.noticeBanner}>
          <Text style={styles.noticeBannerText}>📌 {t('chat.linkedNotice')}</Text>
        </View>
      )}

      <ScrollView
        ref={scrollRef}
        style={styles.messages}
        contentContainerStyle={styles.messagesContent}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd()}
      >
        {/* 빈 상태 + 빠른 질문 칩 */}
        {isEmpty && (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>💬</Text>
            <Text style={styles.emptyText}>{t('chat.emptyHistory')}</Text>
          </View>
        )}

        {isEmpty && chipsVisible && (
          <View style={styles.chips}>
            {quickQuestions.map((q, i) => (
              <TouchableOpacity
                key={i}
                style={styles.chip}
                onPress={() => handleSend(q)}
                activeOpacity={0.7}
              >
                <Text style={styles.chipText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* 메시지 목록 */}
        {allMessages.map((msg, idx) => (
          <View
            key={idx}
            style={[styles.bubble, msg.role === 'user' ? styles.userBubble : styles.aiBubble]}
          >
            <Text style={msg.role === 'user' ? styles.userText : styles.aiText}>
              {msg.content}
            </Text>
          </View>
        ))}

        {/* 타이핑 인디케이터 */}
        {sendMutation.isPending && <TypingIndicator />}
      </ScrollView>

      {/* 입력창 */}
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={message}
          onChangeText={setMessage}
          placeholder={t('chat.placeholder')}
          placeholderTextColor={Colors.disabled}
          multiline
          maxLength={1000}
          returnKeyType="send"
          onSubmitEditing={() => handleSend()}
        />
        <TouchableOpacity
          onPress={() => handleSend()}
          style={[
            styles.sendBtn,
            (!message.trim() || sendMutation.isPending) && styles.sendBtnDisabled,
          ]}
          disabled={!message.trim() || sendMutation.isPending}
          accessibilityLabel={t('chat.send')}
        >
          <Text style={styles.sendIcon}>➤</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container:       { flex: 1, backgroundColor: Colors.background },

  noticeBanner: {
    backgroundColor: Colors.primaryLight,
    paddingVertical:   8,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  noticeBannerText: { fontSize: 13, color: Colors.primary, fontWeight: '600' },

  messages:        { flex: 1 },
  messagesContent: { padding: 16, gap: 8 },

  emptyContainer: { alignItems: 'center', paddingTop: 40 },
  emptyIcon:      { fontSize: 48, marginBottom: 12 },
  emptyText:      { fontSize: 15, color: Colors.textSecondary, textAlign: 'center', lineHeight: 22 },

  chips: { gap: 8, marginTop: 16, marginBottom: 8 },
  chip: {
    backgroundColor: Colors.surface,
    borderWidth:     1,
    borderColor:     Colors.primary,
    borderRadius:    20,
    paddingVertical:   10,
    paddingHorizontal: 14,
  },
  chipText: { fontSize: 14, color: Colors.primary, fontWeight: '500' },

  bubble:     { maxWidth: '80%', borderRadius: 16, padding: 12, marginVertical: 2 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: Colors.primary, borderBottomRightRadius: 4 },
  aiBubble:   {
    alignSelf:       'flex-start',
    backgroundColor: Colors.surface,
    borderWidth:     1,
    borderColor:     Colors.border,
    borderBottomLeftRadius: 4,
  },
  userText: { color: Colors.surface, fontSize: 15, lineHeight: 22 },
  aiText:   { color: Colors.textPrimary, fontSize: 15, lineHeight: 22 },

  inputRow: {
    flexDirection:   'row',
    alignItems:      'flex-end',
    padding:         12,
    gap:             8,
    backgroundColor: Colors.surface,
    borderTopWidth:  1,
    borderTopColor:  Colors.border,
  },
  input: {
    flex:              1,
    minHeight:         44,
    maxHeight:         120,
    borderWidth:       1,
    borderColor:       Colors.border,
    borderRadius:      22,
    paddingHorizontal: 16,
    paddingVertical:   10,
    fontSize:          15,
    backgroundColor:   Colors.background,
    color:             Colors.textPrimary,
  },
  sendBtn: {
    width:           44,
    height:          44,
    borderRadius:    22,
    backgroundColor: Colors.primary,
    alignItems:      'center',
    justifyContent:  'center',
  },
  sendBtnDisabled: { backgroundColor: Colors.disabled },
  sendIcon:        { color: Colors.surface, fontSize: 18 },
});
