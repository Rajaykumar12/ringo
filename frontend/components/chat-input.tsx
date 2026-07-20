import React, { useState } from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  Platform,
  Pressable,
  Image,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import Animated, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';

export interface AttachedImage {
  uri: string;
  mimeType: string;
}

interface ChatInputProps {
  onSendText: (message: string, image?: AttachedImage) => void;
  onSendAudio: () => void;
  onStop: () => void;
  isRecording: boolean;
  isLoading: boolean;
  editingText: string;
  onEditingTextConsumed: () => void;
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
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
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

export function ChatInput({
  onSendText,
  onSendAudio,
  onStop,
  isRecording,
  isLoading,
  editingText,
  onEditingTextConsumed,
}: ChatInputProps) {
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  const [message, setMessage] = useState('');
  const [focused, setFocused] = useState(false);
  const [attachedImage, setAttachedImage] = useState<AttachedImage | null>(null);

  React.useEffect(() => {
    if (editingText) {
      setMessage(editingText);
      onEditingTextConsumed();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingText]);

  const handleSend = () => {
    if ((message.trim() || attachedImage) && !isLoading) {
      onSendText(message.trim(), attachedImage ?? undefined);
      setMessage('');
      setAttachedImage(null);
    }
  };

  const handleAttachImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return;

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      setAttachedImage({ uri: asset.uri, mimeType: asset.mimeType ?? 'image/jpeg' });
    }
  };

  const hasContent = message.trim() || attachedImage;
  const buttonColor = isRecording ? Colors.error : hasContent ? Colors.amber : Colors.teal;
  const buttonIcon = isRecording ? 'stop-circle' : hasContent ? 'send' : 'mic';
  const buttonSize = isRecording || !hasContent ? 24 : 20;

  return (
    <View style={styles.container}>
      {!isLoading && (
        <AnimatedPressable
          onPress={handleAttachImage}
          style={styles.attachButton}
          accessibilityLabel="Attach image"
          accessibilityRole="button"
        >
          <Ionicons name="image-outline" size={22} color={Colors.textFaint} />
        </AnimatedPressable>
      )}
      <View style={[styles.inputWrapper, focused && styles.inputWrapperFocused]}>
        {attachedImage && (
          <View style={styles.imagePreviewRow}>
            <Image source={{ uri: attachedImage.uri }} style={styles.imagePreview} />
            <Pressable
              onPress={() => setAttachedImage(null)}
              accessibilityLabel="Remove attached image"
              accessibilityRole="button"
              style={styles.removeImageButton}
            >
              <Ionicons name="close-circle" size={18} color={Colors.textFaint} />
            </Pressable>
          </View>
        )}
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
        <AnimatedPressable
          onPress={onStop}
          style={[styles.actionButton, styles.loadingButton]}
          accessibilityLabel="Stop generating"
          accessibilityRole="button"
        >
          <Ionicons name="stop" size={18} color={Colors.error} />
        </AnimatedPressable>
      ) : (
        <ActionButton onPress={hasContent ? handleSend : onSendAudio} color={buttonColor}>
          <Ionicons name={buttonIcon as any} size={buttonSize} color="#FFFFFF" />
        </ActionButton>
      )}
    </View>
  );
}

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  container: {
    flexDirection: 'row',
    paddingHorizontal: 14,
    paddingTop: 8,
    paddingBottom: Platform.OS === 'ios' ? 22 : 12,
    backgroundColor: Colors.surface,
    alignItems: 'flex-end',
    gap: 8,
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
  attachButton: {
    width: 40,
    height: 40,
    borderRadius: Radii.full,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 3,
  },
  imagePreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  imagePreview: {
    width: 56,
    height: 56,
    borderRadius: Radii.md,
  },
  removeImageButton: {
    marginLeft: 8,
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
