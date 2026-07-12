import React, { useState } from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Platform,
  Pressable,
} from 'react-native';
import Animated, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii, Shadows } from '@/constants/theme';

interface ChatInputProps {
  onSendText: (message: string) => void;
  onSendAudio: () => void;
  isRecording: boolean;
  isLoading: boolean;
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

function ActionButton({
  onPress,
  color,
  children,
  disabled,
}: {
  onPress: () => void;
  color: string;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  const scale = useSharedValue(1);
  const animStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return (
    <AnimatedPressable
      onPressIn={() => { scale.value = withSpring(0.92, { damping: 15 }); }}
      onPressOut={() => { scale.value = withSpring(1, { damping: 15 }); }}
      onPress={onPress}
      disabled={disabled}
      style={[styles.actionButton, { backgroundColor: color }, animStyle, Shadows.float]}
      accessibilityRole="button"
    >
      {children}
    </AnimatedPressable>
  );
}

export function ChatInput({ onSendText, onSendAudio, isRecording, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [focused, setFocused] = useState(false);

  const handleSend = () => {
    if (message.trim() && !isLoading) {
      onSendText(message.trim());
      setMessage('');
    }
  };

  const buttonColor = isRecording ? Colors.error : message.trim() ? Colors.amber : Colors.teal;
  const buttonIcon = isRecording ? 'stop-circle' : message.trim() ? 'send' : 'mic';
  const buttonSize = isRecording || !message.trim() ? 24 : 20;

  return (
    <View style={styles.container}>
      <View style={[styles.inputWrapper, focused && styles.inputWrapperFocused]}>
        <TextInput
          style={styles.input}
          placeholder="Ask anything…"
          placeholderTextColor={Colors.textFaint}
          value={message}
          onChangeText={setMessage}
          multiline
          maxLength={1000}
          editable={!isLoading}
          onSubmitEditing={Platform.OS !== 'web' ? handleSend : undefined}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          // @ts-ignore — web key interception: Enter sends, Shift+Enter newlines
          onKeyPress={(e: any) => {
            if (Platform.OS === 'web' && e.nativeEvent?.key === 'Enter' && !e.nativeEvent?.shiftKey) {
              e.preventDefault?.();
              handleSend();
            }
          }}
          // @ts-ignore
          {...(Platform.OS === 'web' && { style: [styles.input, { outline: 'none' }] })}
        />
      </View>

      {isLoading ? (
        <View style={[styles.actionButton, styles.loadingButton]}>
          <ActivityIndicator color={Colors.textMuted} size="small" />
        </View>
      ) : (
        <ActionButton onPress={message.trim() ? handleSend : onSendAudio} color={buttonColor}>
          <Ionicons name={buttonIcon as any} size={buttonSize} color="#FFFFFF" />
        </ActionButton>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: Platform.OS === 'ios' ? 26 : 12,
    backgroundColor: Colors.surface,
    alignItems: 'flex-end',
    gap: 10,
    ...Shadows.float,
  },
  inputWrapper: {
    flex: 1,
    backgroundColor: Colors.surfaceWarm,
    borderRadius: Radii.xl,
    borderWidth: 1.5,
    borderColor: Colors.border,
    paddingHorizontal: 16,
    paddingVertical: 10,
    maxHeight: 110,
  },
  inputWrapperFocused: {
    borderColor: Colors.amber,
  },
  input: {
    fontSize: 15,
    color: Colors.text,
    minHeight: 22,
    lineHeight: 22,
  },
  actionButton: {
    width: 46,
    height: 46,
    borderRadius: Radii.full,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingButton: {
    backgroundColor: Colors.surfaceWarm,
  },
});
